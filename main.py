import re
from typing import Annotated

from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlmodel import SQLModel, Field, create_engine, Session, select


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
engine = create_engine("postgresql://roman:12345678@localhost:5432/demoexam0406")

class UserForm(SQLModel, table=True):
    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)
    login: str
    password: str
    fio: str | None
    birth_date: str | None
    phone: str | None
    email: str | None

class RecordForm(SQLModel, table=True):
    __tablename__ = "record"

    id: int | None = Field(default=None, primary_key=True)
    transport: str
    start_date: str
    payment: str
    user_id: int | None = Field(default=None, foreign_key="user.id")
    status: str = Field(default="Новая")


class Review(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    record_id: int = Field(foreign_key="record.id")
    text: str


SQLModel.metadata.create_all(bind=engine)


def get_user_id(request: Request) -> int | None:
    uid = request.cookies.get("user_id")
    return int(uid) if uid else None


@app.get("/")
def root():
    return RedirectResponse("/auth", status_code=302)


@app.get("/auth")
def auth_page(request: Request):
    return templates.TemplateResponse(request, "auth.html", {"error": ""})


@app.get("/registation")
def registation_page(request: Request):
    return templates.TemplateResponse(request, "registation.html", {"errors": []})


@app.get("/record")
def record_page(request: Request):
    if request.cookies.get("role") != "user":
        return RedirectResponse("/auth", status_code=302)
    uid = get_user_id(request)
    with Session(engine) as s:
        records = s.exec(select(RecordForm).where(RecordForm.user_id == uid)).all()
        reviews = s.exec(select(Review).where(Review.user_id == uid)).all()
    return templates.TemplateResponse(request, "record.html", {"records": records, "reviews": reviews})


@app.get("/new_record")
def new_record_page(request: Request):
    if request.cookies.get("role") != "user":
        return RedirectResponse("/auth", status_code=302)
    return templates.TemplateResponse(request, "new_record.html", {})


@app.get("/admin_panel")
def admin_panel_page(request: Request, status: str = ""):
    if request.cookies.get("role") != "Admin":
        return RedirectResponse("/auth", status_code=302)
    with Session(engine) as s:
        q = select(RecordForm)
        if status:
            q = q.where(RecordForm.status == status)
        records = s.exec(q).all()
    return templates.TemplateResponse(request, "admin_panel.html", {"records": records, "status": status})


@app.get("/logout")
def logout():
    response = RedirectResponse("/auth", status_code=302)
    response.delete_cookie("role")
    response.delete_cookie("user_id")
    return response


@app.post("/auth_validation")
def auth_validation(request: Request, data: Annotated[UserForm, Form()]):
    if data.login == "Admin26" and data.password == "Demo20":
        response = RedirectResponse("/admin_panel", status_code=302)
        response.set_cookie("role", "Admin")
        return response

    with Session(engine) as s:
        user = s.exec(select(UserForm).where(UserForm.login == data.login, UserForm.password == data.password)).first()
    if not user:
        return templates.TemplateResponse(request, "auth.html", {"error": "Неверный логин или пароль"})

    response = RedirectResponse("/record", status_code=302)
    response.set_cookie("role", "user")
    response.set_cookie("user_id", str(user.id))
    return response


@app.post("/registation_validation")
def registation_validation(request: Request, data: Annotated[UserForm, Form()]):
    errors = []
    if not re.fullmatch(r"[A-Za-z0-9]{6,}", data.login):
        errors.append("Логин от 6 символов (латиница)")
    if len(data.password) < 8:
        errors.append("Пароль от 8 символов")
    if not re.fullmatch(r"[А-Яа-яЁё ]+", data.fio):
        errors.append("ФИО кириллицей")
    if not re.fullmatch(r"8\(\d{3}\)\d{3}-\d{2}-\d{2}", data.phone):
        errors.append("Телефон 8(XXX)XXX-XX-XX")
    if "@" not in data.email:
        errors.append("Некорректный email")
    if not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", data.birth_date):
        errors.append("Дата ДД.ММ.ГГГГ")

    with Session(engine) as s:
        if s.exec(select(UserForm).where(UserForm.login == data.login)).first():
            errors.append("Логин занят")
        if errors:
            return templates.TemplateResponse(request, "registation.html", {"errors": errors})
        s.add(UserForm(**data.model_dump(exclude={"id"})))
        s.commit()
    return RedirectResponse("/auth", status_code=302)


@app.post("/new_record_validation")
def new_record_validation(request: Request, data: Annotated[RecordForm, Form()]):
    if request.cookies.get("role") != "user":
        return RedirectResponse("/auth", status_code=302)
    with Session(engine) as s:
        s.add(RecordForm(
            user_id=get_user_id(request),
            transport=data.transport,
            start_date=data.start_date,
            payment=data.payment,
        ))
        s.commit()
    return RedirectResponse("/record", status_code=302)


@app.post("/review/{record_id}")
def create_review(record_id: int, request: Request, text: Annotated[str, Form()]):
    if request.cookies.get("role") != "user":
        return RedirectResponse("/auth", status_code=302)
    with Session(engine) as s:
        rec = s.exec(select(RecordForm).where(RecordForm.id == record_id)).first()
        if rec and rec.status != "Новая":
            s.add(Review(user_id=get_user_id(request), record_id=record_id, text=text))
            s.commit()
    return RedirectResponse("/record", status_code=302)


@app.post("/update/{record_id}")
def update_record_status(record_id: int, request: Request, status: Annotated[str, Form()]):
    if request.cookies.get("role") != "Admin":
        return RedirectResponse("/auth", status_code=302)
    with Session(engine) as s:
        rec = s.exec(select(RecordForm).where(RecordForm.id == record_id)).first()
        if rec:
            rec.status = status
            s.add(rec)
            s.commit()
    return RedirectResponse("/admin_panel", status_code=302)
