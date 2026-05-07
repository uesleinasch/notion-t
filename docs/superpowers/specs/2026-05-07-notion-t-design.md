# notion-t — Design

**Data:** 2026-05-07
**Autor:** ueslei.nascimento@jacto.com.br
**Status:** Aprovado para planejamento

## Problema

O usuário usa Notion como sistema principal de notas, mas frequentemente cria anotações
locais na máquina e esquece de transferi-las depois. O resultado é fragmentação: notas
importantes ficam órfãs em arquivos `.txt` espalhados pelo sistema.

## Solução

CLI Python interativa (`notion-t`) que elimina o passo local: o usuário escreve a nota
no `$EDITOR` familiar e ela vai direto para um database "Quick Notes" no Notion.
Sem cache, sem rascunhos persistidos — Notion é a única fonte de verdade.

## Escopo (v1)

**Dentro:**
- REPL interativo com prompt e histórico
- Comandos: `new`, `list`, `open`, `search`, `setup`, `help`, `exit`/`quit`
- Setup wizard no primeiro acesso (token + database)
- Conversão markdown ↔ Notion blocks: parágrafos, headings (`#`/`##`/`###`),
  listas (`-`/`1.`), code fences (```), bold/italic inline, links

**Fora:**
- Tabelas, callouts, toggle, imagens, embeds
- Edição de notas existentes
- Sincronização offline / cache local
- Multi-database / multi-workspace
- Tags na criação (campo reservado no DB para evolução futura)
- Plugins

## Comando e distribuição

- Entry point: `notion-t`
- Pacote Python: `noterminal` (Python ≥ 3.11)
- Distribuição: `pipx install .` (e futuramente `pipx install git+...`)

## Arquitetura

Estrutura em camadas finas — cada módulo tem responsabilidade única e pode ser testado
isoladamente.

```
notion-terminal/
├── pyproject.toml
├── README.md
├── src/noterminal/
│   ├── __init__.py
│   ├── __main__.py         # python -m noterminal
│   ├── repl.py             # loop interativo, prompt, dispatch
│   ├── config.py           # load/save TOML, paths XDG, migração de schema
│   ├── notion_api.py       # único módulo que toca a API
│   ├── markdown.py         # markdown <-> Notion blocks
│   ├── setup_wizard.py     # primeiro acesso
│   └── commands/
│       ├── __init__.py
│       ├── new.py
│       ├── list.py
│       ├── open.py
│       ├── search.py
│       └── help.py
└── tests/
    ├── test_config.py
    ├── test_markdown.py
    ├── test_notion_api.py
    └── test_commands.py
```

**Dependências:**

| Lib | Uso |
|---|---|
| `notion-client` | SDK oficial Notion |
| `prompt_toolkit` | REPL com histórico e autocomplete |
| `rich` | Renderização markdown e tabelas |
| `tomli-w` | Escrita TOML (leitura via `tomllib` nativo) |
| `pytest`, `pytest-mock` | Testes |

## Primeiro acesso (setup wizard)

Disparado quando `~/.config/noterminal/config.toml` não existe ou está corrompido.
Também disponível via comando `setup` no REPL.

```
$ notion-t
notion-t — primeiro acesso detectado.

1) Crie uma integração interna em https://www.notion.so/my-integrations
2) Cole o token aqui (começa com `ntn_` ou `secret_`):
   token> ********
   ✓ token validado (workspace: "Ueslei Pessoal")

3) Onde devem ficar suas notas?
   [1] Usar database existente (cole a URL/ID)
   [2] Criar database "Quick Notes" agora (preciso da URL de uma página onde criar)
   escolha> 2
   página pai (URL)> https://www.notion.so/...
   ✓ database criado: "Quick Notes" (id: abc123…)

config salvo em ~/.config/noterminal/config.toml (chmod 600).

Pronto. Digite `help` para ver comandos.
> _
```

**Garantias:**

- Token validado via `users.me` antes de salvar (sem persistir token inválido).
- Token lido com `getpass` (não vai pro shell history nem é ecoado).
- Database criado com schema correto: campos `Title` (title), `Created` (created_time),
  `Tags` (multi_select).
- Falha 403/404 ao acessar a página pai → instrução clara: *"Vá na página, clique
  em ⋯ → Connections → adicionar [nome-da-integração]"*.

## Comportamento dos comandos

REPL com prompt `> `, histórico via `prompt_toolkit`, autocomplete dos comandos.

### `new`

1. Cria arquivo temporário com template:
   ```
   # Título da nota aqui

   Conteúdo em markdown...
   ```
2. Abre `$EDITOR` (fallback: `nano` → `vi`); usa `editor.command` da config se definido.
3. Após salvar e sair: primeira linha `# ...` vira o título da página, resto vira corpo.
4. Template não-modificado ou arquivo vazio → cancela (similar a `git commit` sem mensagem).
5. Sucesso: `✓ "Título" criado (https://notion.so/...)`.
6. **Se a API falhar após a edição**, o caminho do tempfile é exibido para que o
   conteúdo não se perca.

### `list [N]`

Últimas N notas (default 10) renderizadas com `rich`:

```
#  Título                            Criado
1  Reunião com cliente X             há 2h
2  Ideias para projeto Y             ontem
3  Lista de compras                  6 mai
```

Numeração `#` é estável dentro da sessão — usada por `open <N>` na sequência.

### `open <id|N>`

Aceita ID completo, ID curto (primeiros 8 chars) ou índice `N` da última `list`.
Busca blocos da página, converte para markdown, renderiza com `rich.markdown`.
Mostra URL Notion ao final.

### `search <termo>`

Usa Notion search API filtrada por `database_id` da config. Output igual ao `list`,
com snippet do match.

### `help`, `exit`/`quit`/Ctrl-D, `setup`

`help` — lista comandos resumidos.
`exit`/`quit`/Ctrl-D — encerra REPL.
`setup` — re-executa o wizard (troca token ou database).

## Modelo de dados

### Config: `~/.config/noterminal/config.toml` (chmod 600)

```toml
schema_version = 1

[notion]
token = "ntn_..."
workspace = "Ueslei Pessoal"  # cache só para exibir no startup
database_id = "abc123..."

[editor]
command = ""                  # vazio = usa $EDITOR

[display]
list_size = 10
```

`schema_version` permite migração futura. Config corrompido → backup `.bak` + wizard.

### Notion database "Quick Notes"

| Campo     | Tipo Notion        | Observação                                    |
|-----------|--------------------|-----------------------------------------------|
| `Title`   | `title`            | Obrigatório (todo DB precisa de um `title`)   |
| `Created` | `created_time`     | Preenchido automaticamente pelo Notion        |
| `Tags`    | `multi_select`     | Vazio na v1, reservado para evolução          |

Conteúdo da nota = blocos filhos da página (não uma propriedade). Permite markdown
rico e edição direta no Notion depois.

### Estado em memória do REPL (não persistido)

- `last_listing: list[PageRef]` — populado por `list`/`search`, consumido por `open <N>`.
  Reset a cada nova `list`/`search`.
- `notion_client: Client` — instanciado uma vez no startup pós-wizard.

## Tratamento de erros

| Cenário                              | Comportamento                                                  |
|--------------------------------------|----------------------------------------------------------------|
| Token inválido (401)                 | Mensagem clara + sugestão de `setup`                           |
| Sem permissão na página/DB (403/404) | Instrução para conectar a integração nas Connections           |
| Rate limit (429)                     | Backoff exponencial, 3 tentativas                              |
| Rede off / timeout                   | Falha graciosa; sem retry infinito                             |
| Editor cancelado ou arquivo vazio    | Aborta sem chamar API, mensagem `nota descartada`              |
| API falha após edição                | Mostra caminho do tempfile; conteúdo preservado                |
| Config corrompido                    | Backup `.bak`, re-roda wizard                                  |
| Markdown malformado                  | Parser tolerante; trecho problemático vira parágrafo simples   |

## Testes

| Módulo        | Estratégia                                                       |
|---------------|------------------------------------------------------------------|
| `config`      | Unit: load/save, migração de schema, perm 600, config corrompido |
| `markdown`    | Unit: cada construção markdown → blocks (parágrafo, heading, lista, code, ênfase, link) |
| `notion_api`  | Unit: SDK mockado; verifica payloads enviados e tratamento de exceções |
| `commands`    | Unit: `notion_api` mockado; foco em fluxo de decisão e formatação |
| `setup_wizard`| Unit: prompts mockados (`prompt_toolkit`), validação de token mockada |
| `repl`        | Unit: dispatch correto por comando, tratamento de comando inválido |

Sem testes de integração contra Notion real na v1 (custo de manter > benefício pra projeto solo).

Coverage alvo: > 80% em `config` e `markdown`; > 60% no resto.

## Critérios de sucesso

- `notion-t` arranca em < 2s no segundo acesso (sem latência além da chamada inicial à API).
- `new` → nota visível no Notion em < 5s em rede normal.
- Zero perda de conteúdo: se a API falha após edição, o tempfile sobrevive e o caminho é mostrado.
- Setup wizard concluído em < 2 minutos por um usuário novo.

## Riscos

| Risco                                 | Mitigação                                       |
|---------------------------------------|-------------------------------------------------|
| Mudança breaking na Notion API        | Pin de versão major do `notion-client`          |
| Token vaza no shell history           | `getpass` no wizard (não ecoado, não logado)    |
| Markdown malformado quebra envio      | Parser tolerante; fallback para parágrafo       |
| Permissões de página confusas         | Mensagem de erro com instruções passo-a-passo   |

## Notas de segurança

- Token armazenado em `~/.config/noterminal/config.toml` com permissão `600`.
- Token nunca é logado nem ecoado em prompt.
- O token compartilhado em `project.md` na raiz do repositório **deve ser rotacionado**
  antes do primeiro commit público — recomendação ao usuário durante o setup.
