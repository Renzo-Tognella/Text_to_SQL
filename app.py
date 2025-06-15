#!/usr/bin/env python3
"""
Text2SQL Desktop App - Interface completa com aba do schema
"""

import sys
import time
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import pandas as pd
from text2sql import Text2SQLConverter, connect_db, get_schema, execute_query, get_sample_schema
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

class QueryWorker(QThread):
    """Worker thread para executar queries"""
    
    query_generated = pyqtSignal(str, float)
    query_executed = pyqtSignal(object, object, float)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, converter, nl_query, schema, engine):
        super().__init__()
        self.converter = converter
        self.nl_query = nl_query
        self.schema = schema[0] if isinstance(schema, tuple) else schema
        self.engine = engine
    
    def run(self):
        try:
            start_time = time.time()
            sql_query = self.converter.nl_to_sql(self.nl_query, self.schema)
            generation_time = time.time() - start_time
            
            self.query_generated.emit(sql_query, generation_time)
            
            execution_start = time.time()
            columns, rows = execute_query(self.engine, sql_query)
            execution_time = time.time() - execution_start
            
            self.query_executed.emit(columns, rows, execution_time)
            
        except Exception as e:
            self.error_occurred.emit(str(e))

class ResultsTable(QTableWidget):
    """Tabela customizada para resultados"""
    
    def __init__(self):
        super().__init__()
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSortingEnabled(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def show_context_menu(self, position):
        """Menu de contexto"""
        menu = QMenu(self)
        copy_action = menu.addAction("Copiar")
        export_csv_action = menu.addAction("Exportar CSV")
        
        action = menu.exec_(self.mapToGlobal(position))
        
        if action == copy_action:
            self.copy_selection()
        elif action == export_csv_action:
            self.export_to_csv()
    
    def copy_selection(self):
        """Copia seleção para clipboard"""
        selection = self.selectedRanges()
        if not selection:
            return
            
        text = ""
        for range_item in selection:
            for row in range(range_item.topRow(), range_item.bottomRow() + 1):
                row_data = []
                for col in range(range_item.leftColumn(), range_item.rightColumn() + 1):
                    item = self.item(row, col)
                    row_data.append(item.text() if item else "")
                text += "\t".join(row_data) + "\n"
        
        QApplication.clipboard().setText(text)
    
    def export_to_csv(self):
        """Exporta para CSV"""
        filename, _ = QFileDialog.getSaveFileName(self, "Salvar CSV", 
                                                 f"query_result_{int(time.time())}.csv",
                                                 "CSV Files (*.csv)")
        if filename:
            df = self.get_dataframe()
            df.to_csv(filename, index=False)
            QMessageBox.information(self, "Sucesso", f"Dados exportados para {filename}")
    
    def get_dataframe(self):
        """Converte tabela para DataFrame"""
        headers = []
        for col in range(self.columnCount()):
            headers.append(self.horizontalHeaderItem(col).text())
        
        data = []
        for row in range(self.rowCount()):
            row_data = []
            for col in range(self.columnCount()):
                item = self.item(row, col)
                row_data.append(item.text() if item else "")
            data.append(row_data)
        
        return pd.DataFrame(data, columns=headers)

class SchemaWidget(QWidget):
    """Widget para exibir o schema do banco"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        """Configura a interface do schema"""
        layout = QVBoxLayout()
        
        # Título
        title = QLabel("Schema do Banco de Dados")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Scroll area para as tabelas
        scroll = QScrollArea()
        scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout()
        
        scroll_widget.setLayout(self.scroll_layout)
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        
        layout.addWidget(scroll)
        self.setLayout(layout)
    
    def update_schema(self, schema_details):
        """Atualiza o schema exibido"""
        # Limpa layout anterior
        for i in reversed(range(self.scroll_layout.count())):
            self.scroll_layout.itemAt(i).widget().setParent(None)
        
        # Adiciona cada tabela
        for table_name, columns in schema_details.items():
            table_group = self.create_table_group(table_name, columns)
            self.scroll_layout.addWidget(table_group)
        
        # Adiciona espaço no final
        self.scroll_layout.addStretch()
    
    def create_table_group(self, table_name, columns):
        """Cria um grupo para uma tabela"""
        group = QGroupBox(f"{table_name.upper()}")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Descrições das tabelas
        descriptions = {
            'student': 'Estudantes da universidade',
            'instructor': 'Professores da universidade', 
            'course': 'Cursos oferecidos',
            'takes': 'Notas dos estudantes nos cursos',
            'department': 'Departamentos da universidade',
            'advisor': 'Orientadores dos estudantes',
            'prereq': 'Pré-requisitos dos cursos'
        }
        
        if table_name in descriptions:
            desc_label = QLabel(descriptions[table_name])
            desc_label.setStyleSheet("color: gray; font-style: italic; margin-bottom: 5px;")
            layout.addWidget(desc_label)
        
        # Tabela com colunas
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(['Coluna', 'Tipo'])
        table.setRowCount(len(columns))
        
        for i, (col_name, col_type) in enumerate(columns):
            # Nome da coluna
            name_item = QTableWidgetItem(col_name)
            table.setItem(i, 0, name_item)
            
            # Tipo da coluna
            type_item = QTableWidgetItem(col_type)
            table.setItem(i, 1, type_item)
        
        # Configurações da tabela - aumentando o tamanho
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        
        # Altura maior para mostrar mais linhas sem scroll
        row_height = 30
        header_height = 35
        min_height = header_height + (len(columns) * row_height) + 20
        table.setMinimumHeight(min_height)
        
        # Define altura máxima mais generosa
        max_height = min(600, min_height)  # Máximo de 600px ou altura necessária
        table.setMaximumHeight(max_height)
        
        layout.addWidget(table)
        group.setLayout(layout)
        
        return group

class MainWindow(QMainWindow):
    """Janela principal"""
    
    def __init__(self):
        super().__init__()
        self.engine = None
        self.schema = None
        self.schema_details = None
        self.converter = None
        self.query_history = []
        
        self.setup_ui()
        self.setup_menus()
        self.setup_status_bar()
        self.connect_to_database()
        self.auto_connect_gemini()
    
    def setup_ui(self):
        """Configura interface"""
        self.setWindowTitle("Text2SQL - Google Gemini")
        self.resize(1200, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Sidebar
        sidebar = self.create_sidebar()
        splitter.addWidget(sidebar)
        
        # Área principal
        main_area = self.create_main_area()
        splitter.addWidget(main_area)
        
        splitter.setSizes([250, 950])
    
    def create_sidebar(self):
        """Cria sidebar com exemplos"""
        sidebar = QWidget()
        sidebar.setFixedWidth(250)
        layout = QVBoxLayout()
        
        # Exemplos em português e inglês
        examples_group = QGroupBox("Exemplos")
        examples_layout = QVBoxLayout()
        
        examples = [
            ("Média Economia 2010", "Qual é a média de notas dos cursos de Economia em 2010?"),
            ("Contar Estudantes CS", "Quantos estudantes há em ciência da computação?"),
            ("Maior Salário", "Quem tem o maior salário?"),
            ("Todos os Estudantes", "Mostrar todos os estudantes"),
            ("Listar Professores", "Listar todos os professores")
        ]
        
        for text, query in examples:
            btn = QPushButton(text)
            btn.clicked.connect(lambda checked, q=query: self.set_example_query(q))
            examples_layout.addWidget(btn)
        
        examples_group.setLayout(examples_layout)
        layout.addWidget(examples_group)
        
        layout.addStretch()
        sidebar.setLayout(layout)
        return sidebar
    
    def create_main_area(self):
        """Cria área principal"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Área de consulta
        query_group = QGroupBox("Consulta")
        query_layout = QVBoxLayout()
        
        self.query_input = QTextEdit()
        self.query_input.setPlaceholderText("Digite sua pergunta em português ou inglês...")
        self.query_input.setMaximumHeight(80)
        query_layout.addWidget(self.query_input)
        
        # Botões
        button_layout = QHBoxLayout()
        self.execute_btn = QPushButton("Executar")
        self.execute_btn.clicked.connect(self.execute_query)
        self.execute_btn.setStyleSheet("QPushButton { background-color: #007bff; color: white; padding: 8px; }")
        
        self.clear_btn = QPushButton("Limpar")
        self.clear_btn.clicked.connect(self.clear_query)
        
        button_layout.addWidget(self.execute_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addStretch()
        
        query_layout.addLayout(button_layout)
        query_group.setLayout(query_layout)
        layout.addWidget(query_group)
        
        # Tabs
        self.tab_widget = QTabWidget()
        
        # Tab Resultados
        results_tab = QWidget()
        results_layout = QVBoxLayout()
        
        # SQL gerado
        sql_group = QGroupBox("SQL Gerado")
        sql_layout = QVBoxLayout()
        
        self.sql_display = QTextEdit()
        self.sql_display.setReadOnly(True)
        self.sql_display.setMaximumHeight(100)
        self.sql_display.setStyleSheet("background-color: #2d3748; color: #e2e8f0; font-family: 'Courier New';")
        sql_layout.addWidget(self.sql_display)
        
        sql_group.setLayout(sql_layout)
        results_layout.addWidget(sql_group)
        
        # Tabela de resultados
        results_group = QGroupBox("Resultados")
        table_layout = QVBoxLayout()
        
        self.results_table = ResultsTable()
        table_layout.addWidget(self.results_table)
        
        results_group.setLayout(table_layout)
        results_layout.addWidget(results_group)
        
        results_tab.setLayout(results_layout)
        self.tab_widget.addTab(results_tab, "Resultados")
        
        # Tab Schema
        self.schema_widget = SchemaWidget()
        self.tab_widget.addTab(self.schema_widget, "Schema do Banco")
        
        # Tab Histórico (versão simplificada)
        history_tab = QWidget()
        history_layout = QVBoxLayout()
        
        self.history_list = QListWidget()
        history_layout.addWidget(self.history_list)
        
        history_tab.setLayout(history_layout)
        self.tab_widget.addTab(history_tab, "Histórico")
        
        layout.addWidget(self.tab_widget)
        widget.setLayout(layout)
        return widget
    
    def setup_menus(self):
        """Configura menus"""
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu('Arquivo')
        
        exit_action = QAction('Sair', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        query_menu = menubar.addMenu('Consulta')
        
        execute_action = QAction('Executar', self)
        execute_action.setShortcut('Ctrl+Return')
        execute_action.triggered.connect(self.execute_query)
        query_menu.addAction(execute_action)
    
    def setup_status_bar(self):
        """Configura barra de status"""
        self.status_bar = self.statusBar()
        self.connection_label = QLabel("Desconectado")
        self.query_count_label = QLabel("0 consultas")
        
        self.status_bar.addWidget(self.connection_label)
        self.status_bar.addPermanentWidget(self.query_count_label)
    
    def connect_to_database(self):
        """Conecta ao banco"""
        try:
            self.engine = connect_db()
            self.schema, self.schema_details = get_schema(self.engine)
            self.connection_label.setText("PostgreSQL conectado")
        except Exception as e:
            self.schema, self.schema_details = get_sample_schema()
            self.connection_label.setText("Usando schema de exemplo")
            print(f"Erro DB: {e}")
        
        # Atualiza o widget do schema
        if self.schema_details:
            self.schema_widget.update_schema(self.schema_details)
    
    def auto_connect_gemini(self):
        """Conecta automaticamente ao Gemini usando .env"""
        api_key = os.getenv('GEMINI_API_KEY')
        self.converter = Text2SQLConverter()
    
    def set_example_query(self, query):
        """Define query de exemplo"""
        self.query_input.setPlainText(query)
    
    def clear_query(self):
        """Limpa consulta"""
        self.query_input.clear()
        self.sql_display.clear()
        self.results_table.clear()
        self.results_table.setRowCount(0)
        self.results_table.setColumnCount(0)
    
    def execute_query(self):
        """Executa consulta"""
        if not self.schema:
            QMessageBox.warning(self, "Aviso", "Schema não disponível!")
            return
        
        if not self.converter:
            QMessageBox.warning(self, "Aviso", "Google Gemini não está configurado!")
            return
        
        nl_query = self.query_input.toPlainText().strip()
        if not nl_query:
            QMessageBox.warning(self, "Aviso", "Digite uma pergunta!")
            return
        
        self.clear_query()
        self.query_input.setPlainText(nl_query)
        
        self.execute_btn.setEnabled(False)
        self.execute_btn.setText("Processando...")
        
        schema_for_worker = (self.schema, self.schema_details)
        self.worker = QueryWorker(self.converter, nl_query, schema_for_worker, self.engine)
        self.worker.query_generated.connect(self.on_query_generated)
        self.worker.query_executed.connect(self.on_query_executed)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()
    
    def on_query_generated(self, sql_query, generation_time):
        """Callback quando SQL é gerado"""
        self.sql_display.setPlainText(sql_query)
        self.status_bar.showMessage(f"SQL gerado em {generation_time:.1f}s", 3000)
    
    def on_query_executed(self, columns, rows, execution_time):
        """Callback quando query é executada"""
        self.display_results(columns, rows)
        self.add_to_history(self.query_input.toPlainText(), self.sql_display.toPlainText())
        self.status_bar.showMessage(f"Executado em {execution_time:.2f}s - {len(rows)} resultados", 5000)
    
    def display_results(self, columns, rows):
        """Exibe resultados"""
        self.results_table.setRowCount(len(rows))
        self.results_table.setColumnCount(len(columns))
        self.results_table.setHorizontalHeaderLabels(list(columns))
        
        for row_idx, row_data in enumerate(rows):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                self.results_table.setItem(row_idx, col_idx, item)
        
        self.results_table.resizeColumnsToContents()
        self.tab_widget.setCurrentIndex(0)
    
    def add_to_history(self, nl_query, sql_query):
        """Adiciona ao histórico"""
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {nl_query[:40]}{'...' if len(nl_query) > 40 else ''}"
        self.history_list.addItem(entry)
        self.query_history.append({'nl': nl_query, 'sql': sql_query, 'time': timestamp})
        self.query_count_label.setText(f"{len(self.query_history)} consultas")
    
    def on_error(self, error_message):
        """Callback de erro"""
        QMessageBox.critical(self, "Erro", f"Erro: {error_message}")
    
    def on_worker_finished(self):
        """Callback quando worker termina"""
        self.execute_btn.setEnabled(True)
        self.execute_btn.setText("Executar")

def main():
    """Função principal"""
    app = QApplication(sys.argv)
    app.setApplicationName("Text2SQL - Gemini")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()