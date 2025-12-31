import socket
import ipaddress
import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.poolmanager import PoolManager


def is_disallowed_ip(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
        return any([
            ip.is_private,    # 10.x.x.x, 172.16.x.x, 192.168.x.x
            ip.is_loopback,   # 127.0.0.1
            ip.is_reserved,   
            ip.is_link_local  # 169.254.x.x
        ])
    except ValueError:
        return True
    

class SSRFSafeConnectionMixin:
    def _new_conn(self):
        conn = super()._new_conn()

        try:
            ip_addr = conn.sock.getpeername()[0]
            if is_disallowed_ip(ip_addr):
                conn.close()
                raise requests.exceptions.ConnectTimeout(
                    f"SSRF Detected: Connection to {ip_addr} is blocked"
                )
        except (AttributeError, socket.error):
            pass
        return conn 


class SafeHTTPConnection(SSRFSafeConnectionMixin, HTTPConnection): pass
class SafeHTTPSConnection(SSRFSafeConnectionMixin, HTTPSConnection): pass


class SafeHTTPAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            connection_class=SafeHTTPConnection, # Dùng cho HTTP
            **pool_kwargs
        )

    def proxy_manager_for(self, *args, **kwargs):
        # Tương tự cho trường hợp dùng Proxy
        kwargs['connection_class'] = SafeHTTPSConnection
        return super().proxy_manager_for(*args, **kwargs)

