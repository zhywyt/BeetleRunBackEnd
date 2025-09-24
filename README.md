# BeetleRunBackEnd 
## Quick Start
```bash
pip install fastapi sqlmodel
./start.sh
```

## Register with systemd
```bash
sudo ln -s ${pwd}/beetleRunBk.service /etc/systemd/system/beetleRunBk.service
sudo systemctl daemon-reload
sudo systemctl enable beetleRunBk
sudo systemctl start beetleRunBk
# check the status
sudo systemctl status beetleRunBk
```

## blockly plugin
You can load the blokyly_plugin_bk.txt to koishi-plugin-blockly-null.

It's very fun, yeah?

## API Reference

| 路径         | 方法   | 说明             | 参数/Body         | 返回/渲染页面           |
|--------------|--------|------------------|-------------------|------------------------|
| `/`          | GET    | 数据筛选主页      | -                 | web.html               |
| `/web`       | POST   | 数据筛选API      | user_id, name, min_distance, max_distance | JSON数据           |
| `/stat`      | GET/POST | 用户统计        | user_id           | user_stat.html/JSON    |
| `/bind`      | POST   | 用户绑定         | user_id, name      | bind_success.html / bind_fail.html |
| `/checkin`   | POST   | 打卡             | user_id, distance, ... | 多种打卡成功/失败页面 |
| `/list`      | GET/POST | 打卡记录分页    | user_id, page, size | list.html             |
| `/rank`      | GET    | 排行榜           | -                 | rank.html              |
| `/delete`    | POST   | 删除打卡记录      | user_id           | delete_checkin_success.html / checkin_fail.html |
| `/backup`    | POST   | 数据备份         | -                 | backup_success.html    |
