from wakeonlan import send_magic_packet

def wake(mac: str):
    send_magic_packet(mac)
