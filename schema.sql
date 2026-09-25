-- Schema do Painel do Auditor de Processos de Qualidade (QA Audit Manager).
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projetos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL,
  descricao TEXT,
  responsavel_superior_email TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Em Auditoria',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS participantes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  projeto_id INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
  nome TEXT NOT NULL,
  email TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documentos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  projeto_id INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
  nome_original TEXT NOT NULL,
  caminho_arquivo TEXT NOT NULL,
  tipo TEXT NOT NULL DEFAULT 'inicial', -- legado, não usado mais na UI
  -- Número da versão (1, 2, 3...): cada envio de documento(s) é uma versão
  -- nova, numerada automaticamente — sem o usuário escolher "inicial"/"correção".
  -- A auditoria por IA sempre roda sobre a versão mais recente.
  versao INTEGER NOT NULL DEFAULT 1,
  uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS checklists (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  projeto_id INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
  nome TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS checklist_itens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  checklist_id INTEGER NOT NULL REFERENCES checklists(id) ON DELETE CASCADE,
  codigo TEXT NOT NULL,
  categoria TEXT,
  descricao TEXT NOT NULL,
  ordem INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS auditorias (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  projeto_id INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
  -- NULL = checklist padrão da disciplina (auditoria/criterios.py).
  checklist_id INTEGER REFERENCES checklists(id) ON DELETE SET NULL,
  data_auditoria TEXT NOT NULL DEFAULT (datetime('now')),
  aderencia REAL,
  parecer_final TEXT, -- 'Aprovado' | 'Aprovado com Ressalvas' | 'Reprovado'
  prazo_limite TEXT,
  escalonado INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'em_revisao' -- em_revisao | aguardando_correcao | escalonado | encerrada
);

CREATE TABLE IF NOT EXISTS nao_conformidades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  auditoria_id INTEGER NOT NULL REFERENCES auditorias(id) ON DELETE CASCADE,
  item_checklist TEXT,
  titulo TEXT NOT NULL,
  descricao_erro TEXT NOT NULL,
  evidencia TEXT,
  impacto TEXT,
  acao_corretiva TEXT,
  origem TEXT NOT NULL DEFAULT 'ia', -- 'ia' | 'manual'
  status TEXT NOT NULL DEFAULT 'aberta', -- 'aberta' | 'resolvida'
  prazo_limite TEXT, -- prazo de correção desta NC (notificação é por NC, não por auditoria inteira)
  escalonado INTEGER NOT NULL DEFAULT 0,
  notificado_em TEXT -- quando o prazo foi definido/o e-mail de correção foi preparado
);

CREATE TABLE IF NOT EXISTS logs_emails (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  projeto_id INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
  tipo TEXT NOT NULL, -- 'correcao' | 'escalonamento' | 'fechamento'
  destinatarios TEXT NOT NULL,
  data_envio TEXT NOT NULL DEFAULT (datetime('now')),
  corpo_resumido TEXT
);

CREATE INDEX IF NOT EXISTS idx_participantes_projeto ON participantes(projeto_id);
CREATE INDEX IF NOT EXISTS idx_documentos_projeto ON documentos(projeto_id);
CREATE INDEX IF NOT EXISTS idx_auditorias_projeto ON auditorias(projeto_id);
CREATE INDEX IF NOT EXISTS idx_nc_auditoria ON nao_conformidades(auditoria_id);
CREATE INDEX IF NOT EXISTS idx_logs_projeto ON logs_emails(projeto_id);
CREATE INDEX IF NOT EXISTS idx_checklists_projeto ON checklists(projeto_id);
CREATE INDEX IF NOT EXISTS idx_checklist_itens_checklist ON checklist_itens(checklist_id);
