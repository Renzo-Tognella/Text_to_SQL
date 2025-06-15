# Text2SQL - Google Gemini

Sistema de consulta em linguagem natural para bancos de dados PostgreSQL usando Google Gemini AI.

## Descrição

Aplicação desktop desenvolvida em PyQt5 que permite fazer consultas em bancos de dados PostgreSQL usando linguagem natural em português ou inglês. O sistema utiliza o Google Gemini para converter perguntas em consultas SQL válidas.

## Funcionalidades

- Interface gráfica intuitiva com PyQt5
- Conversão de linguagem natural para SQL usando Google Gemini
- Suporte para português e inglês
- Visualização do schema do banco de dados
- Histórico de consultas realizadas
- Exportação de resultados para CSV
- Conexão com PostgreSQL
- Validação automática de SQL gerado
- Exemplos pré-definidos de consultas

## Estrutura do Projeto

```
trabalho_banco_de_dados/
├── app.py                 # Interface gráfica principal (PyQt5)
├── text2sql.py           # Motor de conversão Text2SQL
├── main.py               # Interface de linha de comando
├── requirements.txt      # Dependências do projeto
├── .env                  # Configurações (não versionado)
└── README.md            # Documentação
```

## Pré-requisitos

- Python 3.8 ou superior
- PostgreSQL 12 ou superior
- Conta Google Cloud com API Gemini habilitada

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/Renzo-Tognella/Text_to_SQL.git
cd Text_to_SQL
```

2. Crie um ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# ou
venv\Scripts\activate     # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

## Configuração

### Banco de Dados PostgreSQL

1. Crie um banco de dados PostgreSQL
2. Configure as credenciais no arquivo `.env`:
```
DB_HOST=localhost
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
DB_NAME=projeto_final
DB_PORT=5432
```

### Google Gemini API

1. Acesse o Google AI Studio - Foi utilizado os tokens gratuitos
2. Gere uma API key
3. Adicione no arquivo `.env`:
```
GEMINI_API_KEY=sua_api_key_aqui
```

## Como Usar

### Interface Gráfica (Recomendado)

```bash
python app.py
```

### Interface de Linha de Comando

```bash
python main.py
```

## Exemplos de Consultas

### Consultas sobre Estudantes
- "Quantos estudantes há em ciência da computação?"
- "Mostrar todos os estudantes"
- "Listar estudantes com mais de 50 créditos"

### Consultas sobre Professores
- "Qual é o maior salário?"
- "Listar todos os professores"
- "Média salarial por departamento"

### Consultas sobre Cursos
- "Quais cursos são oferecidos pelo departamento de Física?"
- "Mostrar cursos com seus créditos"
- "Listar cursos de Economia"

### Consultas sobre Notas
- "Qual é a média de notas dos cursos de Economia em 2010?"
- "Mostrar notas dos estudantes"
- "Estudantes com nota maior que 8"

## Arquitetura do Sistema

### Componentes Principais

1. **Interface Gráfica (app.py)**
   - Desenvolvida em PyQt5
   - Três abas principais: Resultados, Schema, Histórico
   - Sidebar com exemplos de consultas

2. **Motor Text2SQL (text2sql.py)**
   - Integração com Google Gemini
   - Validação de SQL gerado
   - Cache de consultas
   - Tratamento de erros

3. **Conexão com Banco (text2sql.py)**
   - SQLAlchemy para abstração
   - Suporte a PostgreSQL
   - Execução segura de queries

### Fluxo de Funcionamento

1. Usuário digita pergunta em linguagem natural
2. Sistema envia pergunta para Google Gemini com contexto do schema
3. Gemini retorna consulta SQL
4. Sistema valida o SQL gerado
5. SQL é executado no banco de dados
6. Resultados são exibidos na interface
7. Consulta é salva no histórico

## Dependências

### Principais
- **PyQt5**: Interface gráfica
- **google-generativeai**: Integração com Gemini
- **sqlalchemy**: ORM e conexão com banco
- **psycopg2-binary**: Driver PostgreSQL
- **pandas**: Manipulação de dados
- **python-dotenv**: Gerenciamento de variáveis de ambiente

### Desenvolvimento
- **pyinstaller**: Geração de executáveis

## Compilação para Executável

Para gerar um executável standalone:

```bash
pip install pyinstaller
pyinstaller text2sql.spec
```

O executável será gerado em `dist/Text2SQL.app` (macOS) ou `dist/Text2SQL.exe` (Windows).

## Estrutura de Dados

### Schema Universitário

O sistema trabalha com um schema típico de universidade:

- **student**: Informações dos estudantes
- **instructor**: Dados dos professores
- **course**: Catálogo de cursos
- **takes**: Matrículas e notas
- **department**: Departamentos da universidade

## Troubleshooting

### Problemas Comuns

1. **Erro de conexão com PostgreSQL**
   - Verifique se o PostgreSQL está rodando
   - Confirme as credenciais no arquivo `.env`

2. **Erro de API do Gemini**
   - Verifique se a API key está correta
   - Confirme se a API está habilitada no Google Cloud

3. **SQL inválido gerado**
   - O sistema possui validação automática
   - Tente reformular a pergunta de forma mais clara

## Changelog

### Versão 1.0.0
- Interface gráfica completa em PyQt5
- Integração com Google Gemini
- Suporte a PostgreSQL
- Sistema de histórico de consultas
- Exportação de resultados
- Validação automática de SQL