# Implementação — Bolsa Professor (FITGESTAO)

## Regras implementadas
- Instrutor ativo recebe gratuidade integral enquanto a bolsa estiver ativa e dentro da vigência.
- É possível indicar no máximo um familiar por instrutor; o familiar é um cadastro de aluno já existente.
- Um familiar não pode ser vinculado a duas bolsas (restrição única no banco).
- Início e fim opcionais da vigência; suspensão, reativação e encerramento.
- Histórico de criação e mudanças de status, com usuário que realizou a ação.
- Cobranças pendentes existentes dos beneficiários são marcadas como `isento` na concessão; novas cobranças não são criadas e cobranças manuais são bloqueadas.
- A decisão central de acesso facial autoriza o beneficiário com bolsa válida sem exigir matrícula paga.
- Se o cadastro do instrutor for marcado como inativo, a bolsa deixa de liberar acesso; a tela sinaliza que a bolsa precisa ser revisada.

## Arquivos alterados/criados
- `app/models.py`: modelos `ProfessorScholarship` e `ScholarshipEvent`; vigência e relações com os cadastros existentes.
- `app/routes/scholarships.py`: telas/rotas para listar, conceder, suspender, reativar e encerrar.
- `app/templates/scholarships/index.html`: listagem, histórico e ações.
- `app/templates/scholarships/form.html`: formulário de concessão.
- `app/services.py`: função `has_valid_scholarship`, isenção na criação/renovação de matrícula e regra central `access_decision`.
- `app/routes/payments.py`: bloqueio de cobranças manuais para beneficiários ativos.
- `app/__init__.py`: registro das rotas e criação das novas tabelas sem apagar as tabelas existentes.
- `app/templates/base.html`: link Bolsa Professor no menu.
- `app/static/css/style.css`: estilos da tela nova.

## Como testar
1. Faça backup de `instance/academia.db`.
2. Inicie o Flask normalmente e entre com usuário autorizado.
3. Cadastre o instrutor e o familiar em **Alunos** (CPF/documento distinto).
4. Abra **Bolsa Professor > Nova bolsa**, selecione instrutor, familiar e parentesco; defina a vigência.
5. Confira que a bolsa aparece como ativa, que as cobranças pendentes desses beneficiários viraram `isento` e que a tela **Acesso facial** mostra o acesso liberado pela bolsa.
6. Teste suspender, reativar e encerrar; a decisão de acesso deve deixar de autorizar quando suspensa/encerrada.

## Limitações que permanecem
- O projeto atual não possui entidade própria de funcionário/instrutor. Para não tratar qualquer aluno como professor, foi adicionado o campo “É instrutor/professor” ao cadastro de aluno; apenas registros marcados podem receber a bolsa. O desligamento é representado por mudar o cadastro para inativo. Uma futura evolução deve criar cadastro funcional próprio e associá-lo ao usuário de login.
- O projeto ainda não possui isolamento multiacademia (`academy_id`). Portanto, esta implementação vale para a instalação atual de uma academia; não deve ser anunciada como SaaS multi-tenant pronto.
- A autorização é a regra de negócio do sistema. A liberação física da catraca depende do equipamento Control iD e do modo de integração configurado.
