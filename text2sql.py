#!/usr/bin/env python3
"""
Text2SQL com Google Gemini - Sistema simplificado
"""

import os
import sqlalchemy
import google.generativeai as genai
import hashlib
import re
import time
from dotenv import load_dotenv
import argparse

load_dotenv()

# Configurações padrão de conexão
DEFAULT_DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'user': os.getenv('DB_USER', 'renzotognella'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME', 'projeto_final'),
}

class Text2SQLConverter:
    """Text-to-SQL converter usando Google Gemini"""

    def __init__(self, gemini_api_key=None, current_db=None):
        self.gemini_api_key = gemini_api_key or os.getenv('GEMINI_API_KEY')
        self.current_db = current_db or DEFAULT_DB_CONFIG['database']
        self.query_cache = {}
        self.query_count = 0
        self.start_time = time.time()
        
        if self.gemini_api_key and self.gemini_api_key != 'your_api_key_here':
            try:
                genai.configure(api_key=self.gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-lite')
                print("Google Gemini ativado!")
                self.use_gemini = True
            except Exception as e:
                print(f"Erro Gemini: {e}")
                self.use_gemini = False
        else:
            print("⚠️ API key não configurada")
            self.use_gemini = False

    def nl_to_sql(self, nl_query: str, schema: dict) -> str:
        if not self.use_gemini:
            raise Exception("Google Gemini não está configurado. Configure sua API key no arquivo .env")

        cache_key = hashlib.md5(f"{nl_query}_{str(sorted(schema.items()))}".encode()).hexdigest()
        if cache_key in self.query_cache:
            print("Cache hit!")
            return self.query_cache[cache_key]

        elapsed = time.time() - self.start_time
        if self.query_count >= 50 and elapsed < 60:
            time.sleep(60 - elapsed)
            self.start_time = time.time()
            self.query_count = 0

        sql = self._gemini_generate_sql(nl_query, schema)
        self.query_count += 1

        if self._is_valid_sql(sql):
            self.query_cache[cache_key] = sql
            return sql
        else:
            raise Exception("SQL gerado não passou na validação")

    def _gemini_generate_sql(self, nl_query: str, schema: dict) -> str:
        """Geração SQL com Gemini, usando apenas schema quando não for projeto_final"""
        schema_text = self._format_enhanced_schema(schema)

        if self.current_db != 'projeto_final':
            prompt = f"""
            Você é um DBA especialista em PostgreSQL. Abaixo há o esquema completo do banco, com tabelas e colunas.  
            Converta a pergunta em linguagem natural para **uma única** consulta SQL válida, formatada com convenções rígidas:

            • **Palavras-chave em MAIÚSCULAS**: SELECT, FROM, WHERE, JOIN, ON, GROUP BY, ORDER BY, LIMIT, etc.  
            • **Espaço** antes e depois de cada palavra-chave.  
            • **Quebras de linha** entre as principais cláusulas:  
                SELECT …  
                FROM …  
                [JOIN … ON …]  
                WHERE …  
                [GROUP BY …]  
                [ORDER BY …]  
            • **Indentação** de 2 espaços em JOIN/ON.  
            • Termine sempre com ponto-e-vírgula `;`  
            • Não inclua nada além da consulta (sem explicações, sem markdown, sem comentários).

            ESQUEMA DO BANCO:
            {schema_text}

            PERGUNTA: {nl_query}
            """
        else:
            examples = self._get_query_examples()
            prompt = (
                f"Você é um especialista em SQL PostgreSQL. Converta esta pergunta em linguagem natural para uma consulta SQL válida e completa.\n\n"
                f"ESQUEMA DETALHADO DO BANCO DE DADOS:\n{schema_text}\n\n"
                "MAPEAMENTOS DE DEPARTAMENTOS (IMPORTANTE):\n"
                "- \"Economia\" ou \"Economics\" → \"Finance\"\n"
                "- \"Ciência da Computação\" ou \"Computer Science\" → \"Comp. Sci.\"\n"
                "- \"Física\" ou \"Physics\" → \"Physics\"\n"
                "- \"Matemática\" ou \"Mathematics\" → \"Math\"\n\n"
                f"EXEMPLOS DE CONSULTAS VÁLIDAS:\n{examples}\n"
                "REGRAS OBRIGATÓRIAS:\n"
                "1. SEMPRE inclua as cláusulas SELECT e FROM\n"
                "2. Use JOINs quando necessário para conectar tabelas relacionadas\n"
                "3. Para médias de notas: AVG(takes.grade) com JOIN entre takes e course\n"
                "4. Para filtrar por departamento: WHERE course.dept_name = 'Nome_Dept'\n"
                "5. Para filtrar por ano: WHERE takes.year = XXXX\n"
                "6. Use aspas simples para strings: 'Finance', nunca \"Finance\"\n"
                "7. Termine sempre com ponto e vírgula\n"
                "8. Para contagens: COUNT(*) ou COUNT(DISTINCT coluna)\n"
                "9. Para ordenação: ORDER BY coluna DESC/ASC quando apropriado\n"
                "10. NUNCA retorne SQL incompleto ou fragmentado\n\n"
                f"PERGUNTA: {nl_query}\n\n"
                f"Gere apenas o SQL completo e válido (sem explicações, markdown ou comentários):"
            )

        response = self.gemini_model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=300,
                top_p=0.8,
                top_k=40
            )
        )
        sql = response.text.strip()
        sql = self._clean_sql_response(sql)
        return self._fix_quotes(sql)

    def _format_enhanced_schema(self, schema: dict) -> str:
        descriptions = {
            'student': ('Informações dos estudantes da universidade', [
                'id (INTEGER, PRIMARY KEY)',
                'name (VARCHAR)',
                'dept_name (VARCHAR)',
                'tot_cred (INTEGER)' ],
                'Relaciona com department(dept_name), takes(id)'),
            'instructor': ('Informações dos professores', [
                'id (INTEGER, PRIMARY KEY)',
                'name (VARCHAR)',
                'dept_name (VARCHAR)',
                'salary (NUMERIC)' ],
                'Relaciona com department(dept_name)'),
            'course': ('Catálogo de cursos ofertados', [
                'course_id (VARCHAR, PRIMARY KEY)',
                'title (VARCHAR)',
                'dept_name (VARCHAR)',
                'credits (INTEGER)' ],
                'Relaciona com department(dept_name), takes(course_id)'),
            'takes': ('Registro de matrículas e notas', [
                'id (INTEGER)',
                'course_id (VARCHAR)',
                'sec_id (INTEGER)',
                'semester (VARCHAR)',
                'year (INTEGER)',
                'grade (NUMERIC)' ],
                'Relaciona student(id), course(course_id)'),
            'department': ('Departamentos da universidade', [
                'dept_name (VARCHAR, PRIMARY KEY)',
                'building (VARCHAR)',
                'budget (NUMERIC)' ],
                'Relaciona student, instructor, course')
        }
        text = ''
        for table, cols in schema.items():
            if table in descriptions:
                desc, columns, rel = descriptions[table]
                text += f"TABELA {table}: {desc}\n"
                text += "Colunas:\n"
                for col in columns:
                    text += f"  - {col}\n"
                text += f"Relacionamentos: {rel}\n\n"
        return text

    def _get_query_examples(self) -> str:
        return (
            "SELECT AVG(t.grade) FROM takes t JOIN course c ON t.course_id=c.course_id "
            "WHERE c.dept_name='Finance' AND t.year=2024;\n"
            "SELECT COUNT(*) FROM student WHERE dept_name='Comp. Sci.';\n"
            "SELECT name, salary FROM instructor ORDER BY salary DESC;"
        )

    def _clean_sql_response(self, sql: str) -> str:
        if sql.startswith('```'):
            sql = ''.join(line for line in sql.splitlines() if not line.startswith('```'))
        lines = []
        for l in sql.splitlines():
            l = l.strip()
            if l and not l.startswith('--') and not l.startswith('#'):
                lines.append(l)
        sql = ' '.join(lines)
        return sql.rstrip(';') + ';'

    def _is_valid_sql(self, text: str) -> bool:
        t = text.upper().strip()
        return ('SELECT' in t and 'FROM' in t and text.strip().endswith(';')
                and t.find('SELECT') < t.find('FROM')
                and 10 < len(text) < 2000)

    def _fix_quotes(self, sql: str) -> str:
        sql = re.sub(r'"([^"]+)"', r"'\1'", sql)
        return sql

# Conexão com o banco
def connect_db(**overrides):
    cfg = {**DEFAULT_DB_CONFIG, **overrides}
    url = (f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}@"
           f"{cfg['host']}:{cfg['port']}/{cfg['database']}")
    return sqlalchemy.create_engine(url)

# Funções auxiliares
def get_schema(engine):
    insp = sqlalchemy.inspect(engine)
    sch = {}
    for t in insp.get_table_names():
        sch[t] = [c['name'] for c in insp.get_columns(t)]
    return sch

def execute_query(engine, query):
    with engine.connect() as conn:
        res = conn.execute(sqlalchemy.text(query))
        return res.keys(), res.fetchall()

# CLI e execução principal

def parse_args():
    p = argparse.ArgumentParser(description="Text2SQL com Google Gemini")
    p.add_argument('--host', default=DEFAULT_DB_CONFIG['host'])
    p.add_argument('--port', type=int, default=DEFAULT_DB_CONFIG['port'])
    p.add_argument('--user', default=DEFAULT_DB_CONFIG['user'])
    p.add_argument('--password', default=DEFAULT_DB_CONFIG['password'])
    p.add_argument('--database', default=DEFAULT_DB_CONFIG['database'])
    return p.parse_args()

if __name__ == '__main__':
    args = parse_args()
    engine = connect_db(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database
    )
    converter = Text2SQLConverter(current_db=args.database)
    schema = get_schema(engine)
    nl = "qual a média de notas de Economia em 2024?"
    sql = converter.nl_to_sql(nl, schema)
    cols, rows = execute_query(engine, sql)
    print(cols, rows)
