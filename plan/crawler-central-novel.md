# Plano de implementação do crawler Central Novel

## Objetivo

Adicionar à interface web uma fonte Central Novel baseada em Playwright visível, com verificação manual do Cloudflare, descoberta dos capítulos numerados pelo índice e reutilização do pipeline atual de limpeza e geração de EPUB.

## Restrições e decisões

- Suportar somente a interface web nesta etapa; a CLI permanece inalterada.
- Aceitar páginas de série ou capítulo de `https://centralnovel.com`.
- Incluir somente capítulos com ID numérico; ignorar capítulo 0, extras e epílogos.
- Abrir Chromium visível e aguardar interação manual quando o Cloudflare exigir verificação.
- Não usar stealth, solver de CAPTCHA, proxies, fabricação ou exportação de cookies.
- Manter intervalo de aproximadamente 3 segundos, respeitar `robots.txt` e limitar o uso a finalidade pessoal/educacional.
- Preservar as mudanças locais atuais no backend, frontend e testes.

## 1. Criar o contrato de fontes e o adaptador Central Novel

- Criar `ldm_kindler/crawler/sources/base.py` com:
  - `ChapterRef`;
  - protocolo assíncrono de fonte;
  - ciclo de vida `discover_chapters`, `fetch_chapter` e `close`.
- Criar `ldm_kindler/crawler/sources/central_novel.py` para:
  - validar esquema HTTPS e host exato;
  - iniciar um único Playwright/Chromium visível por job;
  - detectar a página de verificação e aguardar, com timeout explícito, até o seletor esperado aparecer;
  - localizar a página da série a partir de uma URL de série ou do breadcrumb/índice de uma página de capítulo;
  - coletar links de `div.ts-chl-collapsible-content a`;
  - aceitar apenas URLs com `-capitulo-<n>`;
  - deduplicar por ID, ordenar e aplicar `start`/`end`;
  - obter o HTML renderizado de cada capítulo com atraso configurado;
  - fechar o navegador em `finally`.
- Adicionar `playwright` ao `requirements.txt`.
- Documentar no `README.md`:
  - instalação com `python -m playwright install chromium`;
  - uso do navegador visível;
  - limites de uso e tratamento do Cloudflare.

## 2. Tornar o parser configurável

- Em `ldm_kindler/crawler/parse.py`, introduzir um perfil de seletores com os valores atuais como padrão.
- Configurar a Central Novel com:
  - título: `h1.entry-title`;
  - conteúdo: `.epcontent.entry-content`;
  - seletores próprios de navegação.
- Remover opções, compartilhamento, anúncios e navegação antes da limpeza.
- Manter `parse_chapter(expected_id, url, html)` compatível com o crawler HTTP atual.
- Permitir que o adaptador forneça um perfil opcional de seletores.

## 3. Isolar o cache por fonte e série

- Estender `ldm_kindler/crawler/persist.py` com namespace sanitizado opcional.
- Preservar os caminhos legados quando nenhum namespace for informado.
- Usar um namespace como:

```text
centralnovel/the-beginning-after-the-end
```

- Impedir colisões entre obras com capítulos de mesmo número.
- Fazer `stats()` e `clear()` contabilizarem e removerem recursivamente arquivos legados e namespaced.
- Manter o contrato atual da tela de cache.

## 4. Integrar a fonte ao job web

- Em `ldm_kindler/api.py`, adicionar ao `JobRequest`:
  - fonte `generic` ou `central_novel`;
  - `source_url` para o novo modo.
- Aplicar validação condicional:
  - modo genérico mantém template/start URL e faixa;
  - Central Novel exige URL válida;
  - início padrão igual a 1;
  - final vazio detecta o último capítulo numérico.
- Extrair a criação da fonte para uma fábrica pequena.
- Fazer `_run_job` consumir o contrato assíncrono e reutilizar:
  - `clean_html`;
  - `EpubBuilder`;
  - logs via WebSocket.
- Serializar jobs da Central Novel com um lock para evitar várias janelas interativas simultâneas.
- Emitir logs para:
  - aguardando vaga;
  - navegador aberto;
  - aguardando verificação;
  - índice descoberto;
  - capítulo processado;
  - navegador fechado.
- Acrescentar em `ldm_kindler/errors.py` códigos para:
  - host inválido;
  - navegador indisponível;
  - timeout da verificação;
  - índice vazio;
  - conteúdo ausente.

## 5. Atualizar a interface web

- Em `frontend/src/views/CrawlView.vue`, adicionar a fonte **Central Novel** ao formulário.
- No novo modo, mostrar:
  - URL da série ou capítulo;
  - capítulo inicial, padrão 1;
  - capítulo final opcional, com indicação “detectar último”;
  - aviso de que uma janela será aberta;
  - campos existentes de metadados e EPUB.
- Ocultar template, overrides e opções específicas do modo genérico.
- Enviar `source: "central_novel"` e `source_url`.
- Não alterar o payload legado do modo genérico.
- Mostrar uma instrução clara enquanto o job aguarda a verificação manual.

## 6. Criar testes e fixtures

- Criar fixtures mínimas em `ldm_kindler/tests/fixtures/central_novel/`:
  - índice;
  - capítulo válido;
  - capítulo extra;
  - página de challenge.
- Criar `ldm_kindler/tests/test_central_novel_source.py` para testar:
  - validação de host;
  - descoberta e ordenação;
  - exclusão de capítulo 0, extras e epílogos;
  - filtro por faixa;
  - deduplicação;
  - timeout;
  - fechamento do navegador.
- Usar mocks; os testes automatizados não devem acessar o site real.
- Ampliar `ldm_kindler/tests/test_parse_and_clean.py` para validar:
  - preservação do texto;
  - remoção de navegação e anúncios;
  - XHTML final.
- Criar `ldm_kindler/tests/test_cache_namespace.py` para validar:
  - isolamento entre séries;
  - sanitização de namespace;
  - estatísticas;
  - limpeza recursiva.
- Criar `ldm_kindler/tests/test_api_job_request.py` para validar:
  - payload genérico;
  - payload Central Novel;
  - compatibilidade retroativa.

## 7. Verificar a entrega

- Executar:

```bash
python -m pytest -q
```

- Compilar o frontend:

```bash
cd frontend
npm run build
```

- Conferir os diagnósticos dos arquivos editados.
- Fazer primeiro um teste manual com os capítulos 1–2.
- Concluir manualmente a verificação na janela, se solicitada.
- Confirmar títulos, conteúdo, namespace de cache e EPUB.
- Testar uma faixa curta que atravesse uma URL especial do índice.
- Somente depois iniciar do capítulo 1 até o último capítulo numérico descoberto.

## Critérios de aceite

- A interface web gera um EPUB com capítulos numerados em ordem.
- O EPUB não contém challenge, anúncios, navegação, capítulo 0, extras ou epílogos.
- O cache não mistura capítulos de outras fontes ou séries.
- O navegador sempre é fechado ao concluir ou falhar.
- Falhas de navegador e verificação aparecem com código e orientação claros.
- O modo genérico atual e a CLI não sofrem regressões.
