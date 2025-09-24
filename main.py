'''
beetleRunBk/main.py
writed by zhywyt at 2025/9/25
coding with utf-8
'''
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Body, Request
import json
from contextlib import asynccontextmanager
from sqlmodel import SQLModel, Field, Session, create_engine, select
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import re
from datetime import datetime, timedelta


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
def get_current_week_range() -> str:
    '''
    return the week range same as 9.22-9.28
    '''
    from datetime import datetime, timedelta
    now = datetime.now()
    start_of_week = now - timedelta(days=now.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    week_label = f"{start_of_week.month}.{start_of_week.day}-{end_of_week.month}.{end_of_week.day}"
    return week_label
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

@app.post("/web")
async def web_query(data: dict):
    user_id = data.get("user_id")
    name = data.get("name")
    min_distance = data.get("min_distance")
    max_distance = data.get("max_distance")
    filters = []
    if user_id:
        try:
            user_id = int(user_id)
            filters.append(CheckIn.user_id == user_id)
        except:
            pass
    if min_distance:
        try:
            filters.append(CheckIn.distance >= float(min_distance))
        except:
            pass
    if max_distance:
        try:
            filters.append(CheckIn.distance <= float(max_distance))
        except:
            pass
    with Session(engine) as session:
        stmt = select(CheckIn)
        if filters:
            for f in filters:
                stmt = stmt.where(f)
        checkins = session.exec(stmt).all()
        # 关联用户姓名
        user_map = {u.user_id: u.name for u in session.exec(select(User)).all()}
        result = []
        for c in checkins:
            if name and user_map.get(c.user_id, "") != name:
                continue
            result.append({
                "user_id": c.user_id,
                "name": user_map.get(c.user_id, ""),
                "date": c.date,
                "distance": c.distance,
                "order": c.order
            })
    return JSONResponse(content={"items": result})
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("web.html", {"request": request})
async def get_user_stat_(user_id, request):
    error = None
    stat = None
    name = None
    if not user_id:
        error = "user_id is required."
    elif not is_binded(user_id):
        error = f"{user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。"
    else:
        stat = get_statistics(user_id)
        with Session(engine) as session:
            user = session.exec(select(User).where(User.user_id == user_id)).first()
            if user:
                name = user.name
    return templates.TemplateResponse("user_stat.html", {
        "request": request,
        "stat": stat,
        "error": error,
        "week_label": get_current_week_range(),
        "name": name,
        "user_id": user_id
    })
@app.post("/stat", response_class=HTMLResponse)
async def get_user_stat(data: dict, request: Request):
    user_id = data.get("user_id")
    return await get_user_stat_(user_id, request)
@app.get("/stat", response_class=HTMLResponse)
async def get_user_stat_get(request: Request):
    user_id = request.query_params.get("user_id")
    return await get_user_stat_(user_id, request)
@app.post("/bind", response_class=HTMLResponse)
async def bind_user(data: BindInfo, request: Request):
    name = data.name
    user_id = data.user_id
    # 检查名字，要求为：中文英文数字组合，不多于二十个字符
    if not re.match(r'^[\w\s_]{1,10}$', name):
        return templates.TemplateResponse("bind_fail.html", {
            "request": request,
            "error": "名字只能包含中文、英文、数字和下划线，且不多于10个字符。"
        })
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
    return templates.TemplateResponse("bind_success.html", {
        "request": request,
        "name": name,
        "user_id": user_id,
        "count": count
    })
@app.post("/checkin", response_class=HTMLResponse)
async def check_in(data: dict, request: Request):
    error = None
    message = None
    if type(data.get("distance")) != float:
        # try to parse 5.08km 5.08公里
        scale = 1
        dist_str = str(data.get("distance"))
        match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(km|公里|千米)', dist_str)
        if not match:
            match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(英里|miles|mile)', dist_str)
            scale = 1.60934
        if not match:
            match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(m|米)', dist_str)
            scale = 0.001
        if match:
            data["distance"] = float(match.group(1))*scale
            if data["distance"] < 0.001:
                error = f"距离必须大于1m，当前距离: {str(data.get('distance'))}km"
            elif data["distance"] > 100:
                error = f"距离过大，请联系管理员手动添加: {str(data.get('distance'))}"
        else:
            error = f"无法解析距离: {str(data.get('distance'))}，示例： 5.08km | 5.08公里 | 21.095千米 | 5000m | 5000米 | 3.1英里 | 3.5mile | 3.8miles"
        if error != None:
            return templates.TemplateResponse("checkin_fail.html", {
                "request": request,
                "stat": None,
                "error": error
            })
    checkin = CheckIn(**data)
    if not is_binded(checkin.user_id):
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "stat": None,
            "error": f"{checkin.user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。"
        })
    # 检查今天是否打过卡了
    with Session(engine) as session:
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        statement = select(CheckIn).where(
            (CheckIn.user_id == checkin.user_id) &
            (CheckIn.date >= start_of_day.strftime("%Y-%m-%d %H:%M:%S"))
        )
        results = session.exec(statement)
        today_checkins = results.all()
        if today_checkins:
            # 删除该记录
            for c in today_checkins:
                session.delete(c)
            session.commit()
            message = f"{checkin.user_id} 今天已经打过卡了，新的打卡记录已覆盖旧记录。"
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
            "message": message,
            "stat": stat,
        })
async def list_checkins_(user_id, page, size, request):
    try:
        page = int(page)
        size = int(size)
    except:
        page = 1
        size = 10
    if type(page) != int or page < 1:
        page = 1
    if not user_id:
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "error": f"user_id is required."
        })
    try:
        user_id = int(user_id)
    except:
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "error": f"user_id must be an integer."
        })
    if not is_binded(user_id):
        return templates.TemplateResponse("checkin_fail.html", {
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
    return templates.TemplateResponse("checkin_fail.html", {
        "request": request,
        "error": f"{user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。"
    })
@app.post("/list", response_class=HTMLResponse)
async def list_checkins(data: dict, request: Request):
    # data: {"user_id": 123456, "page": 1, "size": 10}
    user_id = data.get("user_id")
    page = data.get("page", 1)
    size = data.get("size", 10)
    return await list_checkins_(user_id, page, size, request)
@app.get("/list", response_class=HTMLResponse)
async def list_checkins_get(request: Request):
    # query user_id: ?user_id=123456&page=1&size=10
    user_id = request.query_params.get("user_id")
    page = request.query_params.get("page", 1)
    size = request.query_params.get("size", 10)
    return await list_checkins_(user_id, page, size, request)
@app.get("/rank", response_class=HTMLResponse)
async def get_rank(request: Request):
    from sqlalchemy import func
    with Session(engine) as session:
        # 查询所有用户的总距离
        user_dist = {}
        user_checkin_count = {}
        for row in session.exec(select(CheckIn.user_id, CheckIn.distance)):
            uid = row.user_id
            user_dist[uid] = user_dist.get(uid, 0) + row.distance
            user_checkin_count[uid] = user_checkin_count.get(uid, 0) + 1
        # 查询所有用户姓名
        user_name_map = {u.user_id: u.name for u in session.exec(select(User))}
        # 排序
        sorted_users = sorted(user_dist.items(), key=lambda x: x[1], reverse=True)
        from datetime import datetime, timedelta
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        rank_list = []
        for idx, (user_id, total_distance) in enumerate(sorted_users, 1):
            # 查询该用户本周所有打卡
            week_statement = select(CheckIn).where(
                (CheckIn.user_id == user_id) &
                (CheckIn.date >= start_of_week.strftime("%Y-%m-%d %H:%M:%S"))
            )
            week_checkins = session.exec(week_statement).all()
            week_distance = sum(c.distance for c in week_checkins)
            rank_list.append({
                "user_id": user_id,
                "name": user_name_map.get(user_id, ""),
                "checkin_count": user_checkin_count.get(user_id, 0),
                "week_distance": week_distance,
                "total_distance": total_distance,
                "rank": idx
            })
        return templates.TemplateResponse("rank.html", {
            "request": request,
            "items": rank_list,
            "week_label": get_current_week_range()
        })

@app.post("/delete", response_class=HTMLResponse)
async def delete_checkin(data: dict, request: Request):
    # data: {"user_id":123456}
    user_id = data.get("user_id")
    if type(user_id) != int:
        try:
            user_id = int(user_id)
        except:
            user_id = None
    if not user_id:
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "error": f"user_id is required."
        })
    if not is_binded(user_id):
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "error": f"{user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。"
        })
    deleted_data = []
    with Session(engine) as session:
        # deleted all checkin data
        statement = select(CheckIn).where(CheckIn.user_id == user_id)
        results = session.exec(statement)
        checkins = results.all()
        for checkin in checkins:
            session.delete(checkin)
            deleted_data.append(checkin)
        session.commit()
        return templates.TemplateResponse("delete_checkin_success.html", {
            "request": request,
            "stat": None,
            "deleted_data" : deleted_data,
            "message": f"成功删除 {len(deleted_data)} 条打卡记录。",
        })

        
@app.post("/backup", response_class=HTMLResponse)
async def backup_data(request: Request):
    # backup database and clear current checkins 
    # save the user and bindinfo table
    import os
    import shutil
    from datetime import datetime
    from sqlmodel import text
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"backup_{timestamp}.db")
    shutil.copy("test.db", backup_file)
    # clear checkin table
    with Session(engine) as session:
        sql = 'DELETE FROM checkin'
        session.exec(text(sql))
        session.commit()
        return templates.TemplateResponse("backup_success.html", {
            "request": request,
            "backup_file": backup_file,
            "message": f"数据库已备份到 {backup_file}，并清空了打卡记录。",
        })
    