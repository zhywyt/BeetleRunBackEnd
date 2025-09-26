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
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="/root/beetleRunBk/static"), name="static")
engine = create_engine("sqlite:///test.db")
templates = Jinja2Templates(directory="templates")
date_format = "%Y-%m-%d %H:%M:%S"
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
    now = datetime.now()
    start_of_week = now - timedelta(days=now.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    week_label = f"{start_of_week.month}.{start_of_week.day}-{end_of_week.month}.{end_of_week.day}"
    return week_label
def get_current_month_range() -> str:
    '''
    return the month range same as 9.1-9.30
    '''
    now = datetime.now()
    start_of_month = now.replace(day=1)
    if now.month == 12:
        end_of_month = now.replace(year=now.year+1, month=1, day=1) - timedelta(days=1)
    else:
        end_of_month = now.replace(month=now.month+1, day=1) - timedelta(days=1)
    month_label = f"{start_of_month.month}.{start_of_month.day}-{end_of_month.month}.{end_of_month.day}"
    return month_label
def get_current_total_range() -> str:
    '''
    return the total range of checkin table same as 2023.9.1-2024.9.30
    '''
    with Session(engine) as session:
        statement = select(CheckIn).order_by(CheckIn.date)
        results = session.exec(statement)
        checkins = results.all()
        if not checkins:
            return "无数据"
        start_date = datetime.strptime(checkins[0].date, date_format)
        end_date = datetime.strptime(checkins[-1].date, date_format)
        total_label = f"{start_date.year}.{start_date.month}.{start_date.day}-{end_date.year}.{end_date.month}.{end_date.day}"
        return total_label
def get_today_checkin_users()-> list[int]:
    '''
    return the list of user_id who have checkin today
    '''
    with Session(engine) as session:
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        statement = select(CheckIn).where(CheckIn.date >= start_of_day.strftime(date_format))
        results = session.exec(statement)
        today_checkins = results.all()
        user_ids = list(set([c.user_id for c in today_checkins]))
        return user_ids
def get_statistics(user_id: int)-> dict:
    '''
    return the statistics of user_id
    '''
    with Session(engine) as session:
        statement = select(CheckIn).where(CheckIn.user_id == user_id)
        results = session.exec(statement)
        checkins = results.all()
        total_distance = sum(checkin.distance for checkin in checkins)
        # 计算本周起始日期（周一）
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        # 统计本周打卡数
        week_checkins = [c for c in checkins if datetime.strptime(c.date, date_format) >= start_of_week]
        return {
            "总计打卡次数": len(checkins),
            "本周打卡次数": len(week_checkins),
            "总距离": total_distance,
            "本周距离": sum(c.distance for c in week_checkins)
        }
def is_binded(user_id: int)->bool:
    '''
    check if the user_id is binded
    '''
    with Session(engine) as session:
        statement = select(User).where(User.user_id == user_id)
        results = session.exec(statement)
        user = results.first()
        return user is not None

@app.post("/web")
async def web_query(data: dict):
    '''
    api for query the databse
    '''
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
    '''
    page for root
    '''
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
    '''
    return the user statistic page
    data: {"user_id": 123456}
    '''
    user_id = data.get("user_id")
    return await get_user_stat_(user_id, request)
@app.get("/stat", response_class=HTMLResponse)
async def get_user_stat_get(request: Request):
    '''
    return the user statistic page
    query user_id: ?user_id=123456
    '''
    user_id = request.query_params.get("user_id")
    return await get_user_stat_(user_id, request)
@app.post("/bind", response_class=HTMLResponse)
async def bind_user(data: BindInfo, request: Request):
    '''
    bind the user_id with name
    data: {"user_id": 123456, "name": "zhywyt"}
    '''
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
async def check_in(data: dict, request: Request)-> HTMLResponse:
    '''
    checkin api
    will parse the distance if not float, support format same as: 5.08km 5.08公里 21.095千米 5000m 5000米 3.1英里 3.5mile 3.8miles
    data: {"message_id": 123456, "user_id": 123456, "order": "打卡 10", "distance": 5.08}
    '''
    error = None
    message = None
    start_time = datetime.now()
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
            return templates.TemplateResponse("checkin/checkin_fail.html", {
                "request": request,
                "stat": None,
                "error": error,
                "solve_time": (datetime.now() - start_time).total_seconds(),
            })
    checkin = CheckIn(**data)
    if not is_binded(checkin.user_id):
        return templates.TemplateResponse("checkin/checkin_fail.html", {
            "request": request,
            "stat": None,
            "error": f"{checkin.user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    # check the date if is not UTC+8, convert it to UTC+8
    dt = datetime.strptime(checkin.date, date_format)
    dt = dt + timedelta(hours=8)
    checkin.date = dt.strftime(date_format)
    # 检查今天是否打过卡了
    checked_users = get_today_checkin_users()
    # 检查今天已经打的人数
    checked_user_num = len(checked_users)
    with Session(engine) as session:
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        statement = select(CheckIn).where(
            (CheckIn.user_id == checkin.user_id) &
            (CheckIn.date >= start_of_day.strftime(date_format))
        )
        results = session.exec(statement)
        today_checkins = results.all()
        if today_checkins:
            # 删除该记录
            for c in today_checkins:
                session.delete(c)
            session.commit()
            message = f"{checkin.user_id} 今天已经打过卡了，打卡记录已覆盖。"
    import random
    css_choices = [
        "checkin/checkin.css",
        # "checkin/checkin2.css",
        # "checkin/checkin3.css",
        # "checkin/checkin4.css",
        # "checkin/checkin5.css",
    ]
    chosen_css = request.url_for('static', path=random.choice(css_choices))
    with Session(engine) as session:
        session.add(checkin)
        session.commit()
        session.refresh(checkin)
        stat = get_statistics(checkin.user_id)
        return templates.TemplateResponse("checkin/checkin.html", {
            "request": request,
            "name": session.exec(select(User).where(User.user_id == checkin.user_id)).first().name,
            "mileage": checkin.distance,
            "message": message,
            "today_checkin_count": checked_user_num,
            "css_style_path": chosen_css,
            "stat": stat,
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
async def list_checkins_(user_id, page, size, request)-> HTMLResponse:
    '''
    list the checkins of user_id with pagination
    '''
    start_time = datetime.now()
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
            "error": f"user_id is required.",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    try:
        user_id = int(user_id)
    except:
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "error": f"user_id must be an integer.",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    if not is_binded(user_id):
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "error": f"{user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。",
            "solve_time": (datetime.now() - start_time).total_seconds(),
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
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    return templates.TemplateResponse("checkin_fail.html", {
        "request": request,
        "error": f"{user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。",
        "solve_time": (datetime.now() - start_time).total_seconds(),
    })
@app.post("/list", response_class=HTMLResponse)
async def list_checkins(data: dict, request: Request)->HTMLResponse:
    '''
    list post api
    data: {"user_id": 123456, "page": 1, "size": 10}
    '''
    user_id = data.get("user_id")
    page = data.get("page", 1)
    size = data.get("size", 10)
    return await list_checkins_(user_id, page, size, request)
@app.get("/list", response_class=HTMLResponse)
async def list_checkins_get(request: Request):
    '''
    list get api
    query user_id: ?user_id=123456&page=1&size=10
    '''
    user_id = request.query_params.get("user_id")
    page = request.query_params.get("page", 1)
    size = request.query_params.get("size", 10)
    return await list_checkins_(user_id, page, size, request)
@app.get("/rank", response_class=HTMLResponse)
async def get_rank(request: Request):
    '''
    rank get api
    get the top 10 users by total distance
    '''
    # cal solve time
    start_time = datetime.now()
    with Session(engine) as session:
        rank_data = {}
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        # search all id to name map
        for row in session.exec(select(CheckIn).where(
            (CheckIn.date >= start_of_week.strftime(date_format)))
        ).all():
            if row.user_id not in rank_data:
                temp_data = {}
                temp_data["uid"] = row.user_id
                temp_data["dist"] = row.distance
                temp_data["name"] = session.exec(select(User).where(User.user_id == row.user_id)).first().name
                temp_data["checkin_count"] = 1
                rank_data[row.user_id] = temp_data
            else:
                rank_data[row.user_id]["dist"] += row.distance
                rank_data[row.user_id]["checkin_count"] += 1
        # sorted by week_distance
        rank_data = sorted(rank_data.values(), key=lambda x: x["dist"], reverse=True)[:10]
        rank_list = []
        for idx, data in enumerate(rank_data, 1):
            rank_list.append({
                "user_id": data.get("uid", 0),
                "name": data.get("name", ""),
                "checkin_count": data.get("checkin_count", 0),
                "week_distance": data.get("dist", 0),
                "rank": idx,
            })
        return templates.TemplateResponse("rank.html", {
            "request": request,
            "items": rank_list,
            "week_label": get_current_week_range(),
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
@app.post("/rank", response_class=HTMLResponse)
async def post_rank(data:dict, request: Request):
    '''
    this api for admin, will pick all data but not front of 10
    data: {"mode" : "total" or "month" or "week"}
    '''
    mode = data.get("mode", "month")
    start_time = datetime.now()
    if mode not in ["total", "month", "week"]:
        mode = "month"
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
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        rank_list = []
        label_key = "week_label"
        label = ""
        if mode == "week":
            for idx, (user_id, total_distance) in enumerate(sorted_users, 1):
                # 查询该用户本周所有打卡
                week_statement = select(CheckIn).where(
                    (CheckIn.user_id == user_id) &
                    (CheckIn.date >= start_of_week.strftime(date_format))
                )
                week_checkins = session.exec(week_statement).all()
                week_distance = sum(c.distance for c in week_checkins)
                if week_distance < 1:
                    continue
                rank_list.append({
                    "user_id": user_id,
                    "name": user_name_map.get(user_id, ""),
                    "checkin_count": user_checkin_count.get(user_id, 0),
                    "week_distance": week_distance,
                    "total_distance": total_distance,
                    "rank": idx,
                })
            label_key = "week_label"
            label = get_current_week_range()
        elif mode == "month":
            for idx, (user_id, total_distance) in enumerate(sorted_users, 1):
                month_statement = select(CheckIn).where(
                    (CheckIn.user_id == user_id) &
                    (CheckIn.date >= start_of_month.strftime(date_format))
                )
                month_checkins = session.exec(month_statement).all()
                month_distance = sum(c.distance for c in month_checkins)
                if month_distance < 1:
                    continue
                rank_list.append({
                    "user_id": user_id,
                    "name": user_name_map.get(user_id, ""),
                    "checkin_count": user_checkin_count.get(user_id, 0),
                    "month_distance": month_distance,
                    "total_distance": total_distance,
                    "rank": idx,
                })
            label_key = "month_label"
            label = get_current_month_range()
        elif mode == "total":
            for idx, (user_id, total_distance) in enumerate(sorted_users, 1):
                rank_list.append({
                    "user_id": user_id,
                    "name": user_name_map.get(user_id, ""),
                    "checkin_count": user_checkin_count.get(user_id, 0),
                    "total_distance": total_distance,
                    "rank": idx,
                })
            label_key = "total_label"
            label = get_current_total_range()
        return templates.TemplateResponse("rank.html", {
            "request": request,
            "items": rank_list,
            label_key: label,
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
@app.post("/delete", response_class=HTMLResponse)
async def delete_checkin(data: dict, request: Request):
    '''
    delete all checkin data of user_id
    data: {"user_id":123456}
    '''
    user_id = data.get("user_id")
    start_time = datetime.now()
    if type(user_id) != int:
        try:
            user_id = int(user_id)
        except:
            user_id = None
    if not user_id:
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "error": f"user_id is required.",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    if not is_binded(user_id):
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "error": f"{user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。",
            "solve_time": (datetime.now() - start_time).total_seconds(),
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
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })

        
def backup_data_(request: Request, backup_name=None):
    '''
    only backup data do not clear checkin table
    '''
    import os
    import shutil
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    # there is not parse checkin.date need not date_format var
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if backup_name == None:
        backup_name = timestamp
    backup_file = os.path.join(backup_dir, f"backup_{backup_name}.db")
    shutil.copy("test.db", backup_file)
    return backup_file

@app.post("/backup", response_class=HTMLResponse)
async def backup_data(data: dict, request: Request):
    '''
    backup database only, do not clear checkin table
    '''
    start_time = datetime.now()
    backup_name = data.get("backup_name", None)
    backup_file = backup_data_(request, backup_name)
    return templates.TemplateResponse("backup_success.html", {
        "request": request,
        "backup_file": backup_file,
        "message": f"数据库已备份到 {backup_file}。",
        "solve_time": (datetime.now() - start_time).total_seconds(),
    })
    
@app.post("/archive", response_class=HTMLResponse)
async def archive_data(data: dict, request:Request):
    '''
    backup database and clear current checkins 
    save the user and bindinfo table
    clear checkin table
    '''
    start_time = datetime.now()
    from sqlmodel import text
    backup_name = data.get("backup_name", None)
    backup_file = backup_data_(request, backup_name)
    with Session(engine) as session:
        sql = 'DELETE FROM checkin'
        session.exec(text(sql))
        session.commit()
        return templates.TemplateResponse("backup_success.html", {
            "request": request,
            "backup_file": backup_file,
            "message": f"数据库已备份到 {backup_file}，并清空了打卡记录。",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
