from fastapi import FastAPI, Body, Request
import json
from contextlib import asynccontextmanager
from sqlmodel import SQLModel, Field, Session, create_engine, select
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield

app = FastAPI(lifespan=lifespan)
engine = create_engine("sqlite:///test.db")
templates = Jinja2Templates(directory="templates")

class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True) # used by system
    user_id: int                                    # 
    name: str
class CheckIn(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True) # tick gen id
    date: str                                       # date with format yyyy-MM-dd hh:mm:ss
    message_id: int                                 # message id from qq
    user_id: int                                    # qq user id
    order: str                                      # e.g. 打卡 10
    distance: float                                 # distance in km

class BindInfo(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True) # tick gen id
    date: str                                       # date with format yyyy-MM-dd hh:mm:ss
    message_id: int                                 # message id from qq
    user_id: int
    name: str
def get_statistics(user_id: int):
    import datetime
    from datetime import datetime, timedelta
    with Session(engine) as session:
        statement = select(CheckIn).where(CheckIn.user_id == user_id)
        results = session.exec(statement)
        checkins = results.all()
        total_distance = sum(checkin.distance for checkin in checkins)
        # 计算本周起始日期（周一）
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        # 统计本周打卡数
        week_checkins = [c for c in checkins if datetime.strptime(c.date, "%Y-%m-%d %H:%M:%S") >= start_of_week]
        return {
            "总计打卡次数": len(checkins),
            "本周打卡次数": len(week_checkins),
            "总距离": total_distance,
            "本周距离": sum(c.distance for c in week_checkins)
        }
def is_binded(user_id: int):
    with Session(engine) as session:
        statement = select(User).where(User.user_id == user_id)
        results = session.exec(statement)
        user = results.first()
        return user is not None
@app.post("/stat")
def get_user_stat(data: dict):
    user_id = data.get("user_id")
    if not user_id:
        return {"status": "error", "message": "user_id is required."}
    if not is_binded(user_id):
        return {"status": "error", "message": f"{user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。"}
    stats = get_statistics(user_id)
    return {"status": "success", "message": stats}
@app.post("/bind")
def bind_user(data: BindInfo):
    name = data.name
    user_id = data.user_id
    if is_binded(user_id):
        # 删除User表项，重新绑定
        with Session(engine) as session:
            statement = select(User).where(User.user_id == user_id)
            results = session.exec(statement)
            user = results.first()
            if user:
                session.delete(user)
                session.commit()
    with Session(engine) as session:
        session.add(data)
        session.commit()
        session.refresh(data)
        # 更新User表
        user = User(user_id=user_id, name=name)
        session.add(user)
        session.commit()
        session.refresh(user)
        # 计算当前User表总人数
        count = len(session.exec(select(User)).all())
    return {"status": "success", "message": f"{name} 成功绑定到 {user_id}，当前已绑定总人数：{count}"}
@app.post("/checkin", response_class=HTMLResponse)
async def check_in(data: dict, request: Request):
    checkin = CheckIn(**data)
    print(checkin)
    if not is_binded(checkin.user_id):
        return templates.TemplateResponse("checkin.html", {
            "request": request,
            "stat": None,
            "error": f"{checkin.user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。"
        })
    import random
    template_choices = [
        "checkin.html",
        "checkin2.html",
        "checkin3.html",
        "checkin4.html",
        "checkin5.html",
    ]
    chosen_template = random.choice(template_choices)
    with Session(engine) as session:
        session.add(checkin)
        session.commit()
        session.refresh(checkin)
        stat = get_statistics(checkin.user_id)
        return templates.TemplateResponse(chosen_template, {
            "request": request,
            "name": session.exec(select(User).where(User.user_id == checkin.user_id)).first().name,
            "mileage": checkin.distance,
            "stat": stat,
        })
@app.post("/list", response_class=HTMLResponse)
def list_checkins(data: dict, request: Request):
    # data: {"user_id": 123456, "page": 1, "size": 10}
    user_id = data.get("user_id")
    page = data.get("page", 1)
    size = data.get("size", 10)
    if not user_id:
        return templates.TemplateResponse("checkin.html", {
            "request": request,
            "error": f"user_id is required."
        })
    if not is_binded(user_id):
        return templates.TemplateResponse("checkin.html", {
            "request": request,
            "error": f"{user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。"
        })
    with Session(engine) as session:
        # 统计数量
        maxpage = len(session.exec(select(CheckIn).where(CheckIn.user_id == user_id)).all()) / size
        page = min(page, int(maxpage) + 1)
        statement = select(CheckIn).where(CheckIn.user_id == user_id).offset((page - 1) * size).limit(size)
        results = session.exec(statement)
        checkins = results.all()
        item = [checkin.model_dump() for checkin in checkins]
        return templates.TemplateResponse("list.html", {
            "request": request,
            "items": item,
            "name": session.exec(select(User).where(User.user_id == user_id)).first().name,
            "page": page,
            "maxpage": int(maxpage) + 1,
            "size": size,
            "user_id": user_id,
        })
    return templates.TemplateResponse("checkin.html", {
        "request": request,
        "error": f"{user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。"
    })
@app.get("/rank", response_class=HTMLResponse)
async def get_rank(request: Request):
    from sqlalchemy import func
    with Session(engine) as session:
        statement = (
            select(CheckIn.user_id, User.name, func.count(CheckIn.id).label("checkin_count"))
            .join(User, User.user_id == CheckIn.user_id)
            .group_by(CheckIn.user_id, User.name)
            .order_by(func.count(CheckIn.id).desc())
        )
        results = session.exec(statement)
        raw_list = results.all()
        rank_list = []
        from datetime import datetime, timedelta
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        for idx, row in enumerate(raw_list, 1):
            d = dict(row._mapping)
            # 查询本周距离
            user_id = d["user_id"]
            week_distance = 0.0
            # 查询该用户本周所有打卡
            week_statement = select(CheckIn).where(
                (CheckIn.user_id == user_id) &
                (CheckIn.date >= start_of_week.strftime("%Y-%m-%d %H:%M:%S"))
            )
            week_checkins = session.exec(week_statement).all()
            week_distance = sum(c.distance for c in week_checkins)
            d["week_distance"] = week_distance
            d["rank"] = idx
            rank_list.append(d)
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        week_label = f"{start_of_week.month}.{start_of_week.day}-{end_of_week.month}.{end_of_week.day}"
        return templates.TemplateResponse("rank.html", {
            "request": request,
            "items": rank_list,
            "week_label": week_label
        })