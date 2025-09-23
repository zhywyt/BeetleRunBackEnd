# BeetleRunBackEnd 
## Quick Start
```bash
pip install fastapi sqlmodel
./start.sh
```

## Register with systemd
```bash
sudo ln -s ${pwd}/beetRunBk.service /etc/systemd/system/beetRunBk.service
sudo systemctl daemon-reload
sudo systemctl enable beetRunBk
sudo systemctl start beetRunBk
# check the status
sudo systemctl status beetRunBk
```

## blockly plugin
You can load the blokyly_plugin_bk.txt to koishi-plugin-blockly-null.

It's very fun, yeah?