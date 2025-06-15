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

# Carrega configurações do .env
load_dotenv()

class Text2SQLConverter:
    """Text-to-SQL converter usando Google Gemini"""

    def __init__(self, gemini_api_key=None):
        self.gemini_api_key = gemini_api_key or os.getenv('GEMINI_API_KEY')
        self.query_cache = {}
        self.query_count = 0
        self.start_time = time.time()
        
        if self.gemini_api_key and self.gemini_api_key != 'your_api_key_here':
            try:
                genai.configure(api_key=self.gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-lite')
                print("🌟 Google Gemini ativado!")
                self.use_gemini = True
            except Exception as e:
                print(f"❌ Erro Gemini: {e}")
                self.use_gemini = False
        else:
            print("⚠️ API key não configurada")
            self.use_gemini = False

    def nl_to_sql(self, nl_query: str, schema: dict) -> str:
        """Converte linguagem natural para SQL usando apenas Gemini"""
        if not self.use_gemini:
            raise Exception("Google Gemini não está configurado. Configure sua API key no arquivo .env")
        
        cache_key = hashlib.md5(f"{nl_query}_{str(sorted(schema.items()))}".encode()).hexdigest()
        
        if cache_key in self.query_cache:
            print("⚡ Cache hit!")
            return self.query_cache[cache_key]
        
        # Rate limiting
        elapsed = time.time() - self.start_time
        if self.query_count >= 50 and elapsed < 60:
            time.sleep(60 - elapsed)
            self.start_time = time.time()
            self.query_count = 0
        
        result = self._gemini_generate_sql(nl_query, schema)
        self.query_count += 1
        
        if self._is_valid_sql(result):
            self.query_cache[cache_key] = result
            return result
        else:
            raise Exception("SQL gerado não passou na validação")

    def _gemini_generate_sql(self, nl_query: str, schema: dict) -> str:
        """Geração SQL com Gemini usando prompts melhorados e mais contexto"""
        schema_text = self._format_enhanced_schema(schema)
        examples = self._get_query_examples()
        
        prompt = f"""Você é um especialista em SQL PostgreSQL. Converta esta pergunta em linguagem natural para uma consulta SQL válida e completa.

ESQUEMA DETALHADO DO BANCO DE DADOS:
{schema_text}

MAPEAMENTOS DE DEPARTAMENTOS (IMPORTANTE):
- "Economia" ou "Economics" → "Finance"
- "Ciência da Computação" ou "Computer Science" → "Comp. Sci."
- "Física" ou "Physics" → "Physics"
- "Matemática" ou "Mathematics" → "Math"

EXEMPLOS DE CONSULTAS VÁLIDAS:
{examples}

REGRAS OBRIGATÓRIAS:
1. SEMPRE inclua as cláusulas SELECT e FROM
2. Use JOINs quando necessário para conectar tabelas relacionadas
3. Para médias de notas: AVG(takes.grade) com JOIN entre takes e course
4. Para filtrar por departamento: WHERE course.dept_name = 'Nome_Dept'
5. Para filtrar por ano: WHERE takes.year = XXXX
6. Use aspas simples para strings: 'Finance', nunca "Finance"
7. Termine sempre com ponto e vírgula
8. Para contagens: COUNT(*) ou COUNT(DISTINCT coluna)
9. Para ordenação: ORDER BY coluna DESC/ASC quando apropriado
10. NUNCA retorne SQL incompleto ou fragmentado

PERGUNTA: {nl_query}

Gere apenas o SQL completo e válido (sem explicações, markdown ou comentários):"""

        response = self.gemini_model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,  # Ligeiramente maior para mais criatividade
                max_output_tokens=300,  # Aumentado para consultas mais complexas
                top_p=0.8,
                top_k=40
            )
        )
        
        sql = response.text.strip()
        sql = self._clean_sql_response(sql)
        return self._fix_quotes(sql)

    def _format_enhanced_schema(self, schema: dict) -> str:
        """Formata schema de forma mais detalhada para melhor compreensão"""
        enhanced_descriptions = {
            'student': {
                'desc': 'TABELA: student - Informações dos estudantes da universidade',
                'columns': [
                    'id (INTEGER, PRIMARY KEY) - ID único do estudante',
                    'name (VARCHAR) - Nome completo do estudante', 
                    'dept_name (VARCHAR, FOREIGN KEY) - Nome do departamento do estudante',
                    'tot_cred (INTEGER) - Total de créditos acumulados'
                ],
                'relationships': 'Conecta com: department (dept_name), takes (id)'
            },
            'instructor': {
                'desc': 'TABELA: instructor - Informações dos professores/instrutores',
                'columns': [
                    'id (INTEGER, PRIMARY KEY) - ID único do professor',
                    'name (VARCHAR) - Nome completo do professor',
                    'dept_name (VARCHAR, FOREIGN KEY) - Departamento onde leciona', 
                    'salary (NUMERIC) - Salário do professor'
                ],
                'relationships': 'Conecta com: department (dept_name)'
            },
            'course': {
                'desc': 'TABELA: course - Catálogo de cursos oferecidos',
                'columns': [
                    'course_id (VARCHAR, PRIMARY KEY) - Código identificador do curso',
                    'title (VARCHAR) - Título/nome do curso',
                    'dept_name (VARCHAR, FOREIGN KEY) - Departamento que oferece o curso',
                    'credits (INTEGER) - Número de créditos do curso'
                ],
                'relationships': 'Conecta com: department (dept_name), takes (course_id)'
            },
            'takes': {
                'desc': 'TABELA: takes - Registro de matrículas e notas dos estudantes',
                'columns': [
                    'id (INTEGER, FOREIGN KEY) - ID do estudante matriculado',
                    'course_id (VARCHAR, FOREIGN KEY) - ID do curso matriculado',
                    'sec_id (INTEGER) - ID da seção/turma',
                    'semester (VARCHAR) - Semestre (Fall, Spring, Summer)',
                    'year (INTEGER) - Ano letivo (ex: 2024, 2023)',
                    'grade (NUMERIC) - Nota final do estudante (0-10, pode ser NULL se não avaliado)'
                ],
                'relationships': 'TABELA DE RELACIONAMENTO: conecta student (id) com course (course_id)'
            },
            'department': {
                'desc': 'TABELA: department - Departamentos da universidade',
                'columns': [
                    'dept_name (VARCHAR, PRIMARY KEY) - Nome do departamento',
                    'building (VARCHAR) - Prédio onde fica localizado',
                    'budget (NUMERIC) - Orçamento do departamento'
                ],
                'relationships': 'Conecta com: student, instructor, course (dept_name)'
            }
        }
        
        schema_text = ""
        for table_name in ['student', 'instructor', 'course', 'takes', 'department']:
            if table_name in schema:
                info = enhanced_descriptions[table_name]
                schema_text += f"\n{info['desc']}\n"
                schema_text += "Colunas:\n"
                for col in info['columns']:
                    schema_text += f"  • {col}\n"
                schema_text += f"Relacionamentos: {info['relationships']}\n\n"
        
        return schema_text

    def _get_query_examples(self) -> str:
        """Retorna exemplos de consultas SQL para orientar o Gemini"""
        examples = """
1. Para média de notas por departamento:
   SELECT AVG(t.grade) 
   FROM takes t 
   JOIN course c ON t.course_id = c.course_id 
   WHERE c.dept_name = 'Finance' AND t.year = 2024;

2. Para contar estudantes por departamento:
   SELECT COUNT(*) 
   FROM student 
   WHERE dept_name = 'Comp. Sci.';

3. Para listar professores com salário:
   SELECT name, salary 
   FROM instructor 
   ORDER BY salary DESC;

4. Para cursos de um departamento:
   SELECT title, credits 
   FROM course 
   WHERE dept_name = 'Physics';

5. Para estudantes e suas notas:
   SELECT s.name, c.title, t.grade 
   FROM student s 
   JOIN takes t ON s.id = t.id 
   JOIN course c ON t.course_id = c.course_id 
   WHERE t.year = 2024;
"""
        return examples

    def _clean_sql_response(self, sql: str) -> str:
        """Limpa e normaliza a resposta do Gemini"""
        # Remove markdown se houver
        if sql.startswith('```'):
            lines = sql.split('\n')
            sql_lines = []
            in_code = False
            for line in lines:
                if line.startswith('```'):
                    in_code = not in_code
                    continue
                if in_code or (not line.startswith('```') and 'SELECT' in line.upper()):
                    sql_lines.append(line)
            sql = '\n'.join(sql_lines)
        
        # Remove comentários e texto explicativo
        sql_lines = []
        for line in sql.split('\n'):
            line = line.strip()
            if line and not line.startswith('--') and not line.startswith('#'):
                # Remove texto após o SQL
                if any(word in line.lower() for word in ['explicação:', 'resultado:', 'esta consulta']):
                    break
                sql_lines.append(line)
        
        sql = ' '.join(sql_lines)
        
        # Garante que termina com ponto e vírgula
        sql = sql.rstrip(';').strip() + ';'
        
        return sql

    def _is_valid_sql(self, text: str) -> bool:
        """Validação SQL melhorada"""
        if not text or not isinstance(text, str):
            return False
        
        text_upper = text.upper().strip()
        
        # Verificações básicas obrigatórias
        has_select = "SELECT" in text_upper
        has_from = "FROM" in text_upper
        has_semicolon = text.strip().endswith(';')
        reasonable_length = 10 < len(text) < 2000
        
        # Verificações de estrutura
        select_pos = text_upper.find("SELECT")
        from_pos = text_upper.find("FROM")
        valid_structure = select_pos < from_pos if (select_pos >= 0 and from_pos >= 0) else False
        
        # Não deve ser apenas fragmento
        is_not_fragment = not (text_upper.count('SELECT') == 0 or 
                              text_upper.strip() in ['SELECT AVG(T1.GRADE);', 'SELECT;', 'FROM;'])
        
        return (has_select and has_from and has_semicolon and 
                reasonable_length and valid_structure and is_not_fragment)
    
    def _fix_quotes(self, sql_query: str) -> str:
        """Corrige aspas duplas para simples"""
        patterns = [
            (r'(\s*(?:=|LIKE|IN)\s+)"([^"]+)"', r"\1'\2'"),
            (r'(dept_name\s*=\s*)"([^"]+)"', r"\1'\2'")
        ]
        result = sql_query
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

# Funções utilitárias
def connect_db(host='localhost', user='renzotognella', password=None, database='projeto_final', port=5432):
    """Conecta ao PostgreSQL"""
    if not password:
        password = os.getenv('DB_PASSWORD')
    url = f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}'
    return sqlalchemy.create_engine(url)

def get_schema(engine):
    """Lista tabelas e colunas com tipos"""
    inspector = sqlalchemy.inspect(engine)
    schema = {}
    schema_details = {}
    
    for table in inspector.get_table_names():
        columns = inspector.get_columns(table)
        schema[table] = [col['name'] for col in columns]
        schema_details[table] = [(col['name'], str(col['type'])) for col in columns]
    
    return schema, schema_details

def execute_query(engine, query):
    """Executa SQL"""
    with engine.connect() as conn:
        result = conn.execute(sqlalchemy.text(query))
        return result.keys(), result.fetchall()

def get_sample_schema():
    """Schema de exemplo"""
    schema = {
        'student': ['id', 'name', 'dept_name', 'tot_cred'],
        'instructor': ['id', 'name', 'dept_name', 'salary'],
        'course': ['course_id', 'title', 'dept_name', 'credits'],
        'takes': ['id', 'course_id', 'sec_id', 'semester', 'year', 'grade'],
        'department': ['dept_name', 'building', 'budget']
    }
    
    schema_details = {
        'student': [('id', 'INTEGER'), ('name', 'VARCHAR'), ('dept_name', 'VARCHAR'), ('tot_cred', 'INTEGER')],
        'instructor': [('id', 'INTEGER'), ('name', 'VARCHAR'), ('dept_name', 'VARCHAR'), ('salary', 'NUMERIC')],
        'course': [('course_id', 'VARCHAR'), ('title', 'VARCHAR'), ('dept_name', 'VARCHAR'), ('credits', 'INTEGER')],
        'takes': [('id', 'INTEGER'), ('course_id', 'VARCHAR'), ('sec_id', 'INTEGER'), ('semester', 'VARCHAR'), ('year', 'INTEGER'), ('grade', 'NUMERIC')],
        'department': [('dept_name', 'VARCHAR'), ('building', 'VARCHAR'), ('budget', 'NUMERIC')]
    }
    
    return schema, schema_details