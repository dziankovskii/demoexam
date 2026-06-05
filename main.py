import re

from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlmodel import SQLModel, Field, create_engine, Session, select
from starlette.middleware.sessions import SessionMiddleware


app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="secret")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
engine = create_engine("postgresql://roman:12345678@localhost:5432/demoexam0406")


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    login: str
    password: str
    fio: str
    birth_date: str
    phone: str
    email: str


class Record(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int
    transport: str
    start_date: str
    payment: str
    status: str = "Новая"


class Review(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int
    record_id: int
    text: str


SQLModel.metadata.create_all(bind=engine)


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
    if request.session.get("role") != "user":
        return RedirectResponse("/auth", status_code=302)
    uid = request.session.get("user_id")
    with Session(engine) as s:
        records = s.exec(select(Record).where(Record.user_id == uid)).all()
        reviews = s.exec(select(Review).where(Review.user_id == uid)).all()
    return templates.TemplateResponse(request, "record.html", {"records": records, "reviews": reviews})


@app.get("/new_record")
def new_record_page(request: Request):
    if request.session.get("role") != "user":
        return RedirectResponse("/auth", status_code=302)
    return templates.TemplateResponse(request, "new_record.html", {})


@app.get("/admin_panel")
def admin_panel_page(request: Request, status: str = ""):
    if request.session.get("role") != "Admin":
        return RedirectResponse("/auth", status_code=302)
    with Session(engine) as s:
        q = select(Record)
        if status:
            q = q.where(Record.status == status)
        records = s.exec(q).all()
    return templates.TemplateResponse(request, "admin_panel.html", {"records": records, "status": status})


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/auth", status_code=302)


@app.post("/auth_validation")
def auth_validation(request: Request, login: str = Form(...), password: str = Form(...)):
    if login == "Admin26" and password == "Demo20":
        request.session["role"] = "Admin"
        return RedirectResponse("/admin_panel", status_code=302)

    with Session(engine) as s:
        user = s.exec(select(User).where(User.login == login, User.password == password)).first()
    if not user:
        return templates.TemplateResponse(request, "auth.html", {"error": "Неверный логин или пароль"})

    request.session["role"] = "user"
    request.session["user_id"] = user.id
    return RedirectResponse("/record", status_code=302)


@app.post("/registation_validation")
def registation_validation(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    fio: str = Form(...),
    birth_date: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
):
    errors = []
    if not re.fullmatch(r"[A-Za-z0-9]{6,}", login):
        errors.append("Логин от 6 символов (латиница)")
    if len(password) < 8:
        errors.append("Пароль от 8 символов")
    if not re.fullmatch(r"[А-Яа-яЁё ]+", fio):
        errors.append("ФИО кириллицей")
    if not re.fullmatch(r"8\(\d{3}\)\d{3}-\d{2}-\d{2}", phone):
        errors.append("Телефон 8(XXX)XXX-XX-XX")
    if "@" not in email:
        errors.append("Некорректный email")
    if not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", birth_date):
        errors.append("Дата ДД.ММ.ГГГГ")

    with Session(engine) as s:
        if s.exec(select(User).where(User.login == login)).first():
            errors.append("Логин занят")
        if errors:
            return templates.TemplateResponse(request, "registation.html", {"errors": errors})
        s.add(User(login=login, password=password, fio=fio, birth_date=birth_date, phone=phone, email=email))
        s.commit()
    return RedirectResponse("/auth", status_code=302)


@app.post("/new_record_validation")
def new_record_validation(
    request: Request,
    transport: str = Form(...),
    start_date: str = Form(...),
    payment: str = Form(...),
):
    if request.session.get("role") != "user":
        return RedirectResponse("/auth", status_code=302)
    with Session(engine) as s:
        s.add(Record(
            user_id=request.session["user_id"],
            transport=transport,
            start_date=start_date,
            payment=payment,
        ))
        s.commit()
    return RedirectResponse("/record", status_code=302)


@app.post("/review/{record_id}")
def create_review(record_id: int, request: Request, text: str = Form(...)):
    if request.session.get("role") != "user":
        return RedirectResponse("/auth", status_code=302)
    with Session(engine) as s:
        rec = s.exec(select(Record).where(Record.id == record_id)).first()
        if rec and rec.status != "Новая":
            s.add(Review(user_id=request.session["user_id"], record_id=record_id, text=text))
            s.commit()
    return RedirectResponse("/record", status_code=302)


@app.post("/update/{record_id}")
def update_record_status(record_id: int, request: Request, status: str = Form(...)):
    if request.session.get("role") != "Admin":
        return RedirectResponse("/auth", status_code=302)
    with Session(engine) as s:
        rec = s.exec(select(Record).where(Record.id == record_id)).first()
        if rec:
            rec.status = status
            s.add(rec)
            s.commit()
    return RedirectResponse("/admin_panel", status_code=302)
