# FreeDesktop Secret Service over a private session bus.
import subprocess, tempfile, time
@t(91)
def _():
    import dbus
    from komboe.platform.localvault import LocalVault
    from komboe.platform.secretservice import SERVICE, PATH, SVC, LABEL, ATTRS, serve
    directory = tempfile.mkdtemp(prefix="ksecret-")
    vault = LocalVault(os.path.join(directory, "vault.kdb"), "ss@komboe.test", "local-master-password")
    daemon = subprocess.Popen(["dbus-daemon", "--session", "--print-address", "--nofork"], stdout=subprocess.PIPE, text=True)
    address = daemon.stdout.readline().strip()
    try:
        _service, _thread = serve(address, vault)
        time.sleep(0.3)
        bus = dbus.bus.BusConnection(address)
        remote = dbus.Interface(bus.get_object(SERVICE, PATH), SVC)
        secret = "dbus-secret-" + uuid.uuid4().hex
        props = {LABEL: "Example", ATTRS: dbus.Dictionary({"service": "example.com", "username": "ada"}, signature="ss")}
        item, _prompt = remote.CreateItem(props, ("/", dbus.ByteArray(b""), dbus.ByteArray(secret.encode()), "text/plain"), False)
        unlocked, locked = remote.SearchItems({"service": "example.com"})
        assert str(item) in [str(x) for x in unlocked] and list(locked) == []
        got = dbus.Interface(bus.get_object(SERVICE, item), "org.freedesktop.Secret.Item").GetSecret("/")
        assert bytes(got[2]).decode() == secret
        remote.Lock()
        try:
            dbus.Interface(bus.get_object(SERVICE, item), "org.freedesktop.Secret.Item").GetSecret("/")
            raise AssertionError("locked secret was returned")
        except dbus.exceptions.DBusException:
            pass
        remote.Unlock()
        again = remote.SearchItems({"service": "example.com"})[0]
        got = dbus.Interface(bus.get_object(SERVICE, again[0]), "org.freedesktop.Secret.Item").GetSecret("/")
        assert bytes(got[2]).decode() == secret
        raw = open(vault.path, "rb").read()
        assert secret.encode() not in raw
    finally:
        daemon.terminate()
        vault.close()
    return DONE("Secret Service stores the item in the encrypted local vault and refuses GetSecret while locked")
