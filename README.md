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