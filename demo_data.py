import json
import sys
import urllib.error
import urllib.request

BASE_USERS = "http://127.0.0.1:8001"
BASE_GATEWAY = "http://127.0.0.1:8000"
ADMIN_EMAIL = "admin@helpdesk.com"
ADMIN_PASSWORD = "HelpDesk@2026"
TECH_EMAIL = "tecnico@helpdesk.com"
TECH_PASSWORD = "Tecnico@2026"

def request(base, path, method="GET", data=None, token=None):
    body = None if data is None else json.dumps(data).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(base + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc

def main():
    print("Preparando dados de demonstração...")
    auth = request(BASE_USERS, "/auth/login", "POST",
                   {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    token = auth["access_token"]

    users = request(BASE_USERS, "/users", token=token)
    tech = next((u for u in users if u["email"] == TECH_EMAIL), None)
    if not tech:
        tech = request(BASE_USERS, "/users", "POST", {
            "name": "Carlos Técnico",
            "email": TECH_EMAIL,
            "password": TECH_PASSWORD,
            "role": "technician"
        }, token)
        print("Técnico criado.")
    else:
        print("Técnico já existia.")

    assets = request(BASE_GATEWAY, "/assets", token=token)
    asset = next((a for a in assets if a["asset_tag"] == "PAT-001"), None)
    if not asset:
        asset = request(BASE_GATEWAY, "/assets", "POST", {
            "name": "Notebook Dell",
            "asset_tag": "PAT-001",
            "category": "Notebook",
            "status": "available",
            "description": "Equipamento de demonstração do setor administrativo."
        }, token)
        print("Equipamento criado.")
    else:
        print("Equipamento já existia.")

    tickets = request(BASE_GATEWAY, "/tickets", token=token)
    demo_cases = [
        {
            "title": "Computador não liga",
            "description": "O computador da estação de trabalho não está ligando. Solicito suporte técnico.",
            "priority": "high",
            "asset_id": asset["id"]
        },
        {
            "title": "Instalar pacote Office",
            "description": "Solicito a instalação e configuração do pacote de produtividade neste equipamento.",
            "priority": "normal",
            "asset_id": asset["id"]
        }
    ]

    for item in demo_cases:
        ticket = next((t for t in tickets if t["title"] == item["title"]), None)
        if not ticket:
            ticket = request(BASE_GATEWAY, "/tickets", "POST", item, token)
            tickets.append(ticket)
            print("Chamado criado:", ticket["title"])
        else:
            print("Chamado já existia:", ticket["title"])

        if ticket.get("assigned_to") is None and ticket.get("status") == "open":
            ticket = request(BASE_GATEWAY, f"/tickets/{ticket['id']}", "PATCH",
                             {"assigned_to": tech["id"]}, token)
            print("Chamado atribuído ao técnico:", ticket["title"])

        if not ticket.get("comments"):
            request(BASE_GATEWAY, f"/tickets/{ticket['id']}/comments", "POST",
                    {"text": "Estou verificando a solicitação. Retornarei com a atualização do atendimento."}, token)

    print("")
    print("DEMONSTRAÇÃO PREPARADA!")
    print("Administrador:", ADMIN_EMAIL, "/", ADMIN_PASSWORD)
    print("Técnico:", TECH_EMAIL, "/", TECH_PASSWORD)
    print("Acesse: http://localhost:8000/")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\nNão foi possível concluir a preparação:", exc)
        print("Confira se os quatro serviços estão ligados e tente novamente.")
        sys.exit(1)
