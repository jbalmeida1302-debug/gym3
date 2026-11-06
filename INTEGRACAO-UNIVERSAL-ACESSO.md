# Arquitetura extensível de controle de acesso

O FITGESTAO define um contrato comum em `app/access_adapters.py`. Cada fabricante
precisa de um adaptador próprio para conexão, cadastro facial, atualização de permissão
e leitura de eventos. A integração Control iD existente continua isolada em
`app/controlid.py`; outros fabricantes exigem desenvolvimento e testes próprios.

## Regra central
A função `access_decision(student)` em `app/services.py` verifica aluno ativo,
Bolsa Professor válida, matrícula vigente e inadimplência conforme tolerância do plano.
Pode ser reutilizada por adaptadores que suportem decisão externa em tempo real.

## Limites atuais
- O Histórico de Acessos lista eventos já gravados em `AccessLog`.
- Ações do painel não comprovam passagem física pela catraca.
- Ainda não há receptor universal de eventos: cada fabricante possui formato,
autenticação e mecanismos diferentes.
- Não existe bloqueio físico universal. O bloqueio imediato depende de o equipamento
suportar modo online/decisão externa ou atualização de permissões confiável.
- Não exponha a API do equipamento à internet; use rede local protegida ou VPN.
- Biometria é dado pessoal sensível pela LGPD; definir base legal, transparência,
retenção, controles de acesso e alternativa de identificação.

## Próximas etapas por fabricante
1. Obter modelo, firmware e documentação da API/SDK.
2. Implementar autenticação e adaptador específico.
3. Mapear o aluno para ID externo único; não presumir IDs iguais.
4. Configurar eventos reais, autenticação e deduplicação.
5. Testar liberação e bloqueio físico em ambiente controlado.
6. Só então habilitar produção.
