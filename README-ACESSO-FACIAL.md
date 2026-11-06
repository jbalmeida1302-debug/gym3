# Integração inicial de acesso facial Control iD

## O que foi adicionado
- Menu e página `/acesso-facial`.
- Campos `controlid_user_id` e `face_registered` no cadastro de alunos.
- Histórico de operações solicitadas pelo painel.
- Cliente HTTP separado em `app/controlid.py`.
- Teste de conexão e início de cadastro facial remoto.
- Migração SQLite simples para acrescentar os novos campos sem apagar a base existente.

## Instalação local
1. Faça backup de `instance/academia.db`.
2. Ative seu ambiente virtual.
3. Execute `pip install -r requirements.txt`.
4. Copie `.env.example` para `.env` e preencha as configurações. Gere `SECRET_KEY` aleatória, por exemplo com `python -c "import secrets; print(secrets.token_hex(32))"`.
5. Configure `CONTROLID_BASE_URL` com o endereço base do dispositivo, sem `/login.fcgi`, e credenciais da API.
6. Inicie `python run.py` e acesse `/acesso-facial`.

## Atenção antes de usar em produção
- Este é um primeiro esqueleto de integração, não uma implantação certificada. O fluxo depende do modelo, firmware e modo de operação do terminal.
- A API do equipamento deve ficar em rede local isolada ou VPN; não exponha a porta do terminal diretamente à internet. Se o dispositivo só aceitar HTTP, use `CONTROLID_ALLOW_HTTP=1` apenas numa rede isolada.
- O código usa o ID interno do aluno como `user_id` no dispositivo. Antes de cadastrar, confirme que esse ID não está ocupado por outro usuário na Control iD. Em produção, é preferível manter um mapeamento explícito após confirmar as regras de IDs do equipamento.
- O cadastro remoto síncrono pode ter respostas diferentes conforme firmware. A interface só marca `face_registered` quando a API retorna `success: true`; se a resposta não confirmar, a interface mostra estado pendente para validação no terminal.
- O histórico incluído registra as operações iniciadas pelo painel; ele ainda não recebe automaticamente os eventos reais de passagem/negação da catraca. Para isso, falta configurar o modo de operação e implementar o mecanismo de eventos correspondente ao modelo.
- Nenhum comando de abertura física da catraca foi adicionado. Teste em ambiente controlado e valide a API com o manual específico do equipamento antes de produção.
- Biometria é dado pessoal sensível pela LGPD. Obtenha base legal adequada, informe os titulares, restrinja acesso, defina retenção e ofereça alternativa de acesso quando aplicável.
