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
from text2sql import Text2SQLConverter, connect_db, get_schema, execute_query
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

# Fallback para schema de exemplo

def get_sample_schema():
    schema = {
        'student':    ['id', 'name', 'dept_name', 'tot_cred'],
        'instructor': ['id', 'name', 'dept_name', 'salary'],
        'course':     ['course_id', 'title', 'dept_name', 'credits'],
        'takes':      ['id', 'course_id', 'sec_id', 'semester', 'year', 'grade'],
        'department': ['dept_name', 'building', 'budget']
    }
    # tipos genéricos para exibição
    schema_details = {
        table: [(col, 'VARCHAR') for col in cols]
        for table, cols in schema.items()
    }
    return schema, schema_details

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
        menu = QMenu(self)
        copy_action = menu.addAction("Copiar")
        export_csv_action = menu.addAction("Exportar CSV")
        action = menu.exec_(self.mapToGlobal(position))
        if action == copy_action:
            self.copy_selection()
        elif action == export_csv_action:
            self.export_to_csv()

    def copy_selection(self):
        selection = self.selectedRanges()
        if not selection:
            return
        text = ""
        for r in selection:
            for row in range(r.topRow(), r.bottomRow()+1):
                row_data = [self.item(row, col).text() if self.item(row, col) else "" \
                            for col in range(r.leftColumn(), r.rightColumn()+1)]
                text += "\t".join(row_data) + "\n"
        QApplication.clipboard().setText(text)

    def export_to_csv(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Salvar CSV", \
                                                 f"query_result_{int(time.time())}.csv", \
                                                 "CSV Files (*.csv)")
        if filename:
            df = self.get_dataframe()
            df.to_csv(filename, index=False)
            QMessageBox.information(self, "Sucesso", f"Dados exportados para {filename}")

    def get_dataframe(self):
        headers = [self.horizontalHeaderItem(i).text() for i in range(self.columnCount())]
        data = [[self.item(r, c).text() if self.item(r, c) else "" \
                for c in range(self.columnCount())] for r in range(self.rowCount())]
        return pd.DataFrame(data, columns=headers)

class SchemaWidget(QWidget):
    """Widget para exibir o schema do banco"""
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        title = QLabel("Schema do Banco de Dados")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)

        scroll = QScrollArea()
        container = QWidget()
        self.scroll_layout = QVBoxLayout()
        container.setLayout(self.scroll_layout)
        scroll.setWidget(container)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        self.setLayout(layout)

    def update_schema(self, schema_details):
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        for table, columns in schema_details.items():
            group = QGroupBox(table.upper())
            v = QVBoxLayout()
            tbl = QTableWidget(len(columns), 2)
            tbl.setHorizontalHeaderLabels(['Coluna', 'Tipo'])
            for idx, (col, typ) in enumerate(columns):
                tbl.setItem(idx, 0, QTableWidgetItem(col))
                tbl.setItem(idx, 1, QTableWidgetItem(typ))
            tbl.horizontalHeader().setStretchLastSection(True)
            v.addWidget(tbl)
            group.setLayout(v)
            self.scroll_layout.addWidget(group)
        self.scroll_layout.addStretch()

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
        self.setWindowTitle("Text2SQL - Google Gemini")
        self.resize(1200, 800)
        central = QWidget()
        self.setCentralWidget(central)
        h = QHBoxLayout(central)
        splitter = QSplitter(Qt.Horizontal)
        h.addWidget(splitter)
        splitter.addWidget(self.create_sidebar())
        splitter.addWidget(self.create_main_area())
        splitter.setSizes([250, 950])

    def create_sidebar(self):
        widget = QWidget()
        widget.setFixedWidth(250)
        v = QVBoxLayout(widget)
        grp = QGroupBox("Exemplos")
        lv = QVBoxLayout()
        exemplos = [
            ("Média Economia 2010", "Qual é a média de notas dos cursos de Economia em 2010?"),
            ("Contar Estudantes CS", "Quantos estudantes há em ciência da computação?"),
            ("Maior Salário", "Quem tem o maior salário?"),
            ("Todos os Estudantes", "Mostrar todos os estudantes"),
            ("Listar Professores", "Listar todos os professores")
        ]
        for txt, qry in exemplos:
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, q=qry: self.set_example_query(q))
            lv.addWidget(btn)
        grp.setLayout(lv)
        v.addWidget(grp)
        v.addStretch()
        return widget

    def create_main_area(self):
        widget = QWidget()
        v = QVBoxLayout(widget)
        qgrp = QGroupBox("Consulta")
        ql = QVBoxLayout()
        self.query_input = QTextEdit()
        self.query_input.setPlaceholderText("Digite sua pergunta em português ou inglês...")
        self.query_input.setMaximumHeight(80)
        ql.addWidget(self.query_input)
        bl = QHBoxLayout()
        self.execute_btn = QPushButton("Executar")
        self.execute_btn.clicked.connect(self.execute_query)
        self.clear_btn = QPushButton("Limpar")
        self.clear_btn.clicked.connect(self.clear_query)
        bl.addWidget(self.execute_btn)
        bl.addWidget(self.clear_btn)
        bl.addStretch()
        ql.addLayout(bl)
        qgrp.setLayout(ql)
        v.addWidget(qgrp)

        self.tab_widget = QTabWidget()
        # Resultados tab
        results_tab = QWidget()
        rv = QVBoxLayout(results_tab)
        sql_group = QGroupBox("SQL Gerado")
        sql_layout = QVBoxLayout()
        self.sql_display = QTextEdit()
        self.sql_display.setReadOnly(True)
        self.sql_display.setMaximumHeight(100)
        self.sql_display.setStyleSheet("background-color: #2d3748; color: #e2e8f0; font-family: 'Courier New';")
        sql_layout.addWidget(self.sql_display)
        sql_group.setLayout(sql_layout)
        rv.addWidget(sql_group)
        results_group = QGroupBox("Resultados")
        table_layout = QVBoxLayout()
        self.results_table = ResultsTable()
        table_layout.addWidget(self.results_table)
        results_group.setLayout(table_layout)
        rv.addWidget(results_group)
        results_tab.setLayout(rv)
        self.tab_widget.addTab(results_tab, "Resultados")

        # Schema tab
        self.schema_widget = SchemaWidget()
        self.tab_widget.addTab(self.schema_widget, "Schema do Banco")

        # Histórico tab
        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        self.history_list = QListWidget()
        history_layout.addWidget(self.history_list)
        self.tab_widget.addTab(history_tab, "Histórico")

        v.addWidget(self.tab_widget)
        return widget

    def setup_menus(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu('Arquivo')
        exit_action = QAction('Sair', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        query_menu = menubar.addMenu('Consulta')
        exec_action = QAction('Executar', self)
        exec_action.setShortcut('Ctrl+Return')
        exec_action.triggered.connect(self.execute_query)
        query_menu.addAction(exec_action)

    def setup_status_bar(self):
        self.status_bar = self.statusBar()
        self.connection_label = QLabel("Desconectado")
        self.query_count_label = QLabel("0 consultas")
        self.status_bar.addWidget(self.connection_label)
        self.status_bar.addPermanentWidget(self.query_count_label)

    def connect_to_database(self):
        try:
            self.engine = connect_db()
            self.schema, self.schema_details = get_schema(self.engine)
            self.connection_label.setText("PostgreSQL conectado")
        except Exception as e:
            print(f"Erro DB: {e}")
            self.schema, self.schema_details = get_sample_schema()
            self.connection_label.setText("Usando schema de exemplo")
        if self.schema_details:
            self.schema_widget.update_schema(self.schema_details)

    def auto_connect_gemini(self):
        self.converter = Text2SQLConverter()

    def set_example_query(self, query):
        self.query_input.setPlainText(query)

    def clear_query(self):
        self.query_input.clear()
        self.sql_display.clear()
        self.results_table.clear()
        self.results_table.setRowCount(0)
        self.results_table.setColumnCount(0)

    def execute_query(self):
        if not self.schema:
            QMessageBox.warning(self, "Aviso", "Schema não disponível!")
            return
        if not self.converter or not self.converter.use_gemini:
            QMessageBox.warning(self, "Aviso", "Google Gemini não está configurado!")
            return
        nl_query = self.query_input.toPlainText().strip()
        if not nl_query:
            QMessageBox.warning(self, "Aviso", "Digite uma pergunta!")
            return
        self.clear_query()
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
        self.sql_display.setPlainText(sql_query)
        self.status_bar.showMessage(f"SQL gerado em {generation_time:.1f}s", 3000)

    def on_query_executed(self, columns, rows, execution_time):
        self.display_results(columns, rows)
        self.add_to_history(self.query_input.toPlainText(), self.sql_display.toPlainText())
        selfstatus = f"Executado em {execution_time:.2f}s - {len(rows)} resultados"
        self.status_bar.showMessage(selfstatus, 5000)

    def display_results(self, columns, rows):
        self.results_table.setRowCount(len(rows))
        self.results_table.setColumnCount(len(columns))
        self.results_table.setHorizontalHeaderLabels(list(columns))
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                self.results_table.setItem(r_idx, c_idx, QTableWidgetItem(str(val)))
        self.results_table.resizeColumnsToContents()
        self.tab_widget.setCurrentIndex(0)

    def add_to_history(self, nl_query, sql_query):
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {nl_query[:40]}{'...' if len(nl_query)>40 else ''}"
        self.history_list.addItem(entry)
        self.query_history.append({'nl': nl_query, 'sql': sql_query, 'time': timestamp})
        self.query_count_label.setText(f"{len(self.query_history)} consultas")

    def on_error(self, msg):
        QMessageBox.critical(self, "Erro", f"Erro: {msg}")

    def on_worker_finished(self):
        self.execute_btn.setEnabled(True)
        self.execute_btn.setText("Executar")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Text2SQL - Gemini")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
