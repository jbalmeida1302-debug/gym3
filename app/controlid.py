"""Cliente mínimo para a API Control iD Access.

Configure CONTROLID_BASE_URL, CONTROLID_USERNAME e CONTROLID_PASSWORD no ambiente.
Não exponha a API do equipamento à internet; prefira rede local isolada/VPN.
"""
import os
import requests


class ControlIDError(RuntimeError):
    pass


class ControlIDClient:
    def __init__(self):
        self.base_url = os.getenv("CONTROLID_BASE_URL", "").strip().rstrip("/")
        self.username = os.getenv("CONTROLID_USERNAME", "").strip()
        self.password = os.getenv("CONTROLID_PASSWORD", "")
        if not self.base_url or not self.username or not self.password:
            raise ControlIDError(
                "Configure CONTROLID_BASE_URL, CONTROLID_USERNAME e CONTROLID_PASSWORD."
            )
        if not self.base_url.startswith("https://") and not os.getenv("CONTROLID_ALLOW_HTTP", "0") == "1":
            raise ControlIDError("Use HTTPS ou, se o dispositivo só suportar HTTP, habilite CONTROLID_ALLOW_HTTP=1 apenas em rede local isolada.")
        self.http = requests.Session()
        self.http.trust_env = False
        self.session = None

    def _request(self, method, endpoint, *, params=None, json=None, data=None):
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self.http.request(method, url, params=params, json=json, data=data, timeout=(3, 12))
        except requests.RequestException as exc:
            raise ControlIDError(f"Não foi possível comunicar com a Control iD: {exc.__class__.__name__}.") from exc
        if not response.ok:
            raise ControlIDError(f"A Control iD retornou HTTP {response.status_code} em {endpoint}.")
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text[:300]}

    def login(self):
        result = self._request("POST", "login.fcgi", json={"login": self.username, "password": self.password})
        token = result.get("session")
        if not token:
            raise ControlIDError("Login não retornou uma sessão. Confira as credenciais e o modelo/API do equipamento.")
        self.session = token
        return token

    def call(self, method, endpoint, *, params=None, json=None, data=None):
        if not self.session:
            self.login()
        query = dict(params or {})
        query["session"] = self.session
        return self._request(method, endpoint, params=query, json=json, data=data)

    def test_connection(self):
        self.login()
        return True

    def ensure_user(self, user_id, name):
        # create_objects cria o usuário no terminal. Se já existir, tenta atualizar.
        payload = {"object": "users", "values": [{"id": int(user_id), "name": name}]}
        try:
            self.call("POST", "create_objects.fcgi", json=payload)
        except ControlIDError:
            self.call("POST", "modify_objects.fcgi", json={
                "object": "users", "where": {"users": {"id": int(user_id)}},
                "values": {"name": name}
            })

    def enroll_face(self, user_id):
        return self.call("POST", "remote_enroll.fcgi", json={
            "type": "face", "user_id": int(user_id), "save": True,
            "sync": True, "auto": True, "countdown": 3
        })
