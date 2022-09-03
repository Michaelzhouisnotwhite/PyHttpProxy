# PyHttpProxy


[![OSCS Status](https://www.oscs1024.com/platform/badge/Michaelzhouisnotwhite/PyHttpProxy.svg?size=small)](https://www.oscs1024.com/project/Michaelzhouisnotwhite/PyHttpProxy?ref=badge_small)

**description**: It's a python multithread project only for http proxy

## Get Started

```powershell
python main.py
```

It will default listen on port: 8080.

To change the port, you can:

```python
from server import ProxyServer

ProxyServer(port=1080).start()
```

**NOTE:** if anyone can make this project available for Https request, I would be very appreciate.

