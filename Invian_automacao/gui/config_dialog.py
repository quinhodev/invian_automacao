# gui/config_dialog.py
import tkinter as tk
import os
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import pandas as pd
import threading
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import CAMINHO_EXCEL, ABA_EXCEL, COLUNA_HORARIO, LINHA_INICIAL_EXCEL, HEADLESS, VALOR_ANUNCIANTES_POR_DIA

class ConfigDialog:
    def __init__(self, parent=None):
        self.result = None
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self._setup_window()
        self._build_ui()
        self._load_defaults()
        self._center_window()
        self._load_sheets_async()
    def _setup_window(self):
        self.root.title('🤖 Invian Automation - Configuração')
        self.root.minsize(560, 420)
        self.root.resizable(True, True)
        self.root.grab_set()
    def _build_ui(self):
        main_frame = self._criar_area_rolavel()
        ttk.Label(main_frame, text='Configuração da Automação Invian', font=('Segoe UI', 14, 'bold')).pack(pady=(0, 20))
        tipo_frame = ttk.LabelFrame(main_frame, text='📋 Tipo de Automação', padding='15')
        tipo_frame.pack(fill=tk.X, pady=(0, 15))
        self.tipo_var = tk.StringVar(value='unidades')
        ttk.Radiobutton(tipo_frame, text='🏢 Unidades — Atualizar Horários', variable=self.tipo_var, value='unidades', command=self._on_tipo_change).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(tipo_frame, text='🎯 Faces — Ajustar Anunciantes por Dia', variable=self.tipo_var, value='faces', command=self._on_tipo_change).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(tipo_frame, text='🔄 Ambos — Executar Unidades e Faces', variable=self.tipo_var, value='ambos', command=self._on_tipo_change).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(tipo_frame, text='🏪 Panvel — Criar Unidade (Panvel)', variable=self.tipo_var, value='panvel', command=self._on_tipo_change).pack(anchor=tk.W, pady=2)

        # Frame de anunciantes por dia (apenas Faces / Ambos)
        self.anunciantes_frame = ttk.LabelFrame(main_frame, text='🎯 Anunciantes por Dia (Faces)', padding='15')
        self.anunciantes_frame.pack(fill=tk.X, pady=(0, 15))
        anunciantes_inner = ttk.Frame(self.anunciantes_frame)
        anunciantes_inner.pack(fill=tk.X)
        ttk.Label(anunciantes_inner, text='Quantidade:').pack(side=tk.LEFT, padx=(0, 10))
        self.anunciantes_var = tk.IntVar(value=VALOR_ANUNCIANTES_POR_DIA)
        ttk.Spinbox(anunciantes_inner, from_=1, to=999, textvariable=self.anunciantes_var, width=10).pack(side=tk.LEFT)
        ttk.Label(anunciantes_inner, text='  (valor usado no campo "Anunciantes por dia" das faces)', foreground='gray').pack(side=tk.LEFT, padx=(10, 0))

        # Frame de credenciais
        cred_frame = ttk.LabelFrame(main_frame, text='🔐 Credenciais Invian', padding='15')
        cred_frame.pack(fill=tk.X, pady=(0, 15))
        cred_inner = ttk.Frame(cred_frame)
        cred_inner.pack(fill=tk.X)
        ttk.Label(cred_inner, text='E-mail:').grid(row=0, column=0, sticky=tk.W, pady=2)
        self.email_var = tk.StringVar(value=os.getenv('INVIAN_EMAIL', ''))
        ttk.Entry(cred_inner, textvariable=self.email_var, width=50).grid(row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=2)
        ttk.Label(cred_inner, text='Senha:').grid(row=1, column=0, sticky=tk.W, pady=2)
        self.senha_var = tk.StringVar(value=os.getenv('INVIAN_SENHA', ''))
        ttk.Entry(cred_inner, textvariable=self.senha_var, width=50, show='•').grid(row=1, column=1, sticky=tk.EW, padx=(10, 0), pady=2)
        cred_inner.columnconfigure(1, weight=1)
        ttk.Label(cred_frame, text='💡 Ou defina INVIAN_EMAIL e INVIAN_SENHA como variáveis de ambiente', foreground='gray', font=('Segoe UI', 8)).pack(anchor=tk.W, pady=(5, 0))
        
        arquivo_frame = ttk.LabelFrame(main_frame, text='📁 Arquivo Excel', padding='15')
        arquivo_frame.pack(fill=tk.X, pady=(0, 15))
        arquivo_inner = ttk.Frame(arquivo_frame)
        arquivo_inner.pack(fill=tk.X)
        self.arquivo_var = tk.StringVar()
        ttk.Entry(arquivo_inner, textvariable=self.arquivo_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Button(arquivo_inner, text='📂 Procurar', command=self._selecionar_arquivo).pack(side=tk.RIGHT)
        self.arquivo_info_var = tk.StringVar(value='')
        ttk.Label(arquivo_frame, textvariable=self.arquivo_info_var, foreground='gray').pack(anchor=tk.W, pady=(5, 0))
        self.aba_frame = aba_frame = ttk.LabelFrame(main_frame, text='📑 Aba da Planilha', padding='15')
        aba_frame.pack(fill=tk.X, pady=(0, 15))
        aba_inner = ttk.Frame(aba_frame)
        aba_inner.pack(fill=tk.X)
        self.aba_var = tk.StringVar()
        self.aba_combo = ttk.Combobox(aba_inner, textvariable=self.aba_var, state='readonly', width=47)
        self.aba_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.aba_combo.bind('<<ComboboxSelected>>', self._on_aba_change)
        ttk.Button(aba_inner, text='🔄 Recarregar', command=self._load_sheets_async).pack(side=tk.RIGHT)
        self.aba_info_var = tk.StringVar(value='Selecione um arquivo Excel')
        ttk.Label(aba_frame, textvariable=self.aba_info_var, foreground='gray').pack(anchor=tk.W, pady=(5, 0))
        
        # Frame para seleção de coluna (aparece após carregar aba)
        self.coluna_frame = ttk.LabelFrame(main_frame, text='📊 Coluna para Busca', padding='15')
        self.coluna_frame.pack(fill=tk.X, pady=(0, 15))
        coluna_inner = ttk.Frame(self.coluna_frame)
        coluna_inner.pack(fill=tk.X)
        ttk.Label(coluna_inner, text='Nome do player/face:').pack(side=tk.LEFT)
        self.coluna_var = tk.StringVar()
        self.coluna_combo = ttk.Combobox(coluna_inner, textvariable=self.coluna_var, state='readonly', width=47)
        self.coluna_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        self.horario_row = ttk.Frame(self.coluna_frame)
        self.horario_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(self.horario_row, text='Horário de funcionamento:').pack(side=tk.LEFT)
        self.coluna_horario_var = tk.StringVar()
        self.coluna_horario_combo = ttk.Combobox(self.horario_row, textvariable=self.coluna_horario_var, state='readonly', width=47)
        self.coluna_horario_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        self.coluna_info_var = tk.StringVar(value='Selecione uma aba primeiro')
        ttk.Label(self.coluna_frame, textvariable=self.coluna_info_var, foreground='gray').pack(anchor=tk.W, pady=(5, 0))
        self.coluna_frame.pack_forget()  # Esconde inicialmente
        
        linha_frame = ttk.LabelFrame(main_frame, text='🔢 Linha Inicial', padding='15')
        linha_frame.pack(fill=tk.X, pady=(0, 15))
        linha_inner = ttk.Frame(linha_frame)
        linha_inner.pack(fill=tk.X)
        ttk.Label(linha_inner, text='Linha inicial (1 = cabeçalho):').pack(side=tk.LEFT)
        self.linha_var = tk.IntVar(value=150)
        ttk.Spinbox(linha_inner, from_=1, to=10000, textvariable=self.linha_var, width=10).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Label(linha_frame, text='Dica: a automação nunca começa acima da 1ª linha de dados (abaixo do cabeçalho).', foreground='gray', font=('Segoe UI', 8)).pack(anchor=tk.W, pady=(5, 0))
        nav_frame = ttk.LabelFrame(main_frame, text='👁️ Modo do Navegador', padding='15')
        nav_frame.pack(fill=tk.X, pady=(0, 15))
        self.headless_var = tk.BooleanVar(value=False)
        ttk.Radiobutton(nav_frame, text='🖥️ Visível (debug)', variable=self.headless_var, value=False).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(nav_frame, text='⚡ Headless (produção)', variable=self.headless_var, value=True).pack(anchor=tk.W, pady=2)
        # Frame dos botões - empacotado PRIMEIRO no BOTTOM para ficar fixo no rodapé
        btn_frame = self.footer  # rodapé fixo: os botões ficam sempre visíveis
        self.btn_iniciar = ttk.Button(btn_frame, text='▶ INICIAR AUTOMAÇÃO', command=self._confirmar)
        self.btn_iniciar.pack(side=tk.RIGHT, padx=(10, 0), ipadx=20, ipady=8)
        ttk.Button(btn_frame, text='❌ Cancelar', command=self._cancelar).pack(side=tk.RIGHT, ipadx=15, ipady=8)
        # Estilo para destacar o botão iniciar
        style = ttk.Style()
        style.configure('Accent.TButton', font=('Segoe UI', 10, 'bold'))
        self.btn_iniciar.configure(style='Accent.TButton')
        
        # Log frame - empacotado DEPOIS, expande no espaço restante
        log_frame = ttk.LabelFrame(main_frame, text='📝 Log', padding='10')
        log_frame.pack(fill=tk.X, pady=(10, 0))
        self.log_text = tk.Text(log_frame, height=7, wrap=tk.WORD, font=('Consolas', 9))
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scroll.set, state=tk.DISABLED)
        self._quebrar_textos_longos(main_frame)

    def _quebrar_textos_longos(self, widget):
        """Evita que um texto comprido (lista de colunas) alargue a janela além da tela."""
        for filho in widget.winfo_children():
            if isinstance(filho, ttk.Label):
                filho.configure(wraplength=620, justify=tk.LEFT)
            self._quebrar_textos_longos(filho)

    def _load_defaults(self):
        self.arquivo_var.set(str(CAMINHO_EXCEL))
        self.aba_var.set(ABA_EXCEL)
        self.linha_var.set(LINHA_INICIAL_EXCEL)
        self.headless_var.set(HEADLESS)
        self._log(f'Arquivo padrão: {CAMINHO_EXCEL.name}')
        self._log(f'Aba padrão: {ABA_EXCEL}')
        self._log(f'Linha inicial padrão: {LINHA_INICIAL_EXCEL}')
    def _criar_area_rolavel(self):
        """Rodapé fixo embaixo + conteúdo rolável (barra lateral e roda do mouse)."""
        self.footer = ttk.Frame(self.root, padding=(20, 10))
        self.footer.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Separator(self.root, orient='horizontal').pack(side=tk.BOTTOM, fill=tk.X)

        container = ttk.Frame(self.root)
        container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(container, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        conteudo = ttk.Frame(self.canvas, padding=20)
        janela = self.canvas.create_window((0, 0), window=conteudo, anchor='nw')
        conteudo.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(janela, width=e.width))
        self._conteudo = conteudo

        def _roda(event):
            if self.canvas.yview() == (0.0, 1.0):  # tudo cabe: nada para rolar
                return
            if getattr(event, 'num', None) == 4:
                self.canvas.yview_scroll(-1, 'units')
            elif getattr(event, 'num', None) == 5:
                self.canvas.yview_scroll(1, 'units')
            else:
                self.canvas.yview_scroll(int(-event.delta / 120) or (-1 if event.delta > 0 else 1), 'units')

        for ev in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            self.root.bind(ev, _roda)
        return conteudo

    def _ajustar_tamanho(self, centralizar=False):
        """Ajusta a janela ao conteúdo, limitada a 90% da tela (o resto rola)."""
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w = min(max(self._conteudo.winfo_reqwidth() + 30, 680), 860, int(sw * 0.9))
        h = min(self._conteudo.winfo_reqheight() + self.footer.winfo_reqheight() + 10, int(sh * 0.9))
        if not centralizar and self.root.state() != 'normal':
            return  # maximizada: deixa como está
        x, y = self.root.winfo_x(), self.root.winfo_y()
        if centralizar or x < 0 or y < 0 or x + w > sw or y + h > sh:
            x, y = max((sw - w) // 2, 0), max((sh - h) // 3, 0)
        self.root.geometry(f'{w}x{h}+{x}+{y}')

    def _center_window(self):
        self._ajustar_tamanho(centralizar=True)
    def _log(self, msg):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f'{msg}\n')
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    def _selecionar_arquivo(self):
        arquivo = filedialog.askopenfilename(
            title='Selecionar arquivo Excel',
            filetypes=[('Excel files', '*.xlsx *.xls'), ('Todos', '*.*')],
            initialdir=Path(self.arquivo_var.get()).parent if self.arquivo_var.get() else '.')
        if arquivo:
            self.arquivo_var.set(arquivo)
            self._log(f'Arquivo selecionado: {Path(arquivo).name}')
            self._load_sheets_async()

    def _load_sheets_async(self):
        self.btn_iniciar.config(state=tk.DISABLED)
        self.aba_combo.config(state=tk.DISABLED)
        atual = self.aba_var.get()
        if atual and atual != 'Carregando...':
            self._aba_preferida = atual  # lembra a aba (ex.: ONSIGN) para reselecionar depois
        self.aba_var.set('Carregando...')
        self._log('Lendo planilha...')
        def worker():
            try:
                arquivo = self.arquivo_var.get()
                if not arquivo or not Path(arquivo).exists():
                    raise FileNotFoundError('Arquivo não encontrado')
                xls = pd.ExcelFile(arquivo)
                abas = xls.sheet_names
                self.root.after(0, lambda: self._on_sheets_loaded(abas, arquivo))
            except Exception as e:
                msg = str(e)
                self.root.after(0, lambda m=msg: self._on_sheets_error(m))
        threading.Thread(target=worker, daemon=True).start()

    def _on_sheets_loaded(self, abas, arquivo):
        self.aba_combo['values'] = abas
        self.aba_combo.config(state='readonly')
        aba_atual = getattr(self, '_aba_preferida', None) or ABA_EXCEL
        if aba_atual in abas:
            self.aba_combo.set(aba_atual)
        else:
            self.aba_combo.set(abas[0])
        self.btn_iniciar.config(state=tk.NORMAL)
        self._log('Abas encontradas: ' + ', '.join(abas))
        self._on_aba_change()

    def _on_sheets_error(self, erro):
        self.aba_combo.config(state='readonly')
        self.aba_combo['values'] = []
        self.aba_var.set('')
        self.btn_iniciar.config(state=tk.NORMAL)
        self._log(f'[ERRO] Erro ao ler planilha: {erro}')
        messagebox.showerror('Erro', f'Não foi possível ler o arquivo Excel:\n{erro}')

    def _on_aba_change(self, event=None):
        aba = self.aba_var.get()
        arquivo = self.arquivo_var.get()
        if aba and arquivo and Path(arquivo).exists():
            try:
                self._linha_cabecalho = 1
                # Primeira tentativa: lê normalmente (header=0 = primeira linha)
                df = pd.read_excel(arquivo, sheet_name=aba, nrows=5, header=0)
                cols = list(df.columns)
                
                # Se tiver colunas "Unnamed", tenta detectar header real lendo mais linhas
                unnamed_count = sum(1 for c in cols if str(c).startswith('Unnamed'))
                if unnamed_count > len(cols) * 0.5:  # Mais de 50% unnamed
                    # Tenta ler sem header para ver estrutura
                    df_raw = pd.read_excel(arquivo, sheet_name=aba, nrows=10, header=None)
                    # Procura linha que parece cabeçalho (menos vazios, mais texto)
                    best_header_row = 0
                    best_score = -1
                    for i, row in df_raw.iterrows():
                        non_empty = sum(1 for v in row if pd.notna(v) and str(v).strip())
                        text_like = sum(1 for v in row if pd.notna(v) and isinstance(v, str) and len(str(v).strip()) > 1)
                        score = non_empty + text_like
                        if score > best_score:
                            best_score = score
                            best_header_row = i
                    
                    if best_header_row > 0:
                        self._linha_cabecalho = int(best_header_row) + 1
                        df = pd.read_excel(arquivo, sheet_name=aba, nrows=5, header=best_header_row)
                        cols = list(df.columns)
                
                # Limpa nomes: remove "Unnamed: X", strip espaços
                cols_clean = []
                for c in cols:
                    c_str = str(c).strip()
                    if c_str and not c_str.startswith('Unnamed'):
                        cols_clean.append(c_str)
                
                if not cols_clean:
                    cols_clean = [str(c).strip() for c in cols if str(c).strip()]
                
                self.aba_info_var.set(f'Colunas: {", ".join(cols_clean[:8])}{"..." if len(cols_clean) > 8 else ""} | {len(cols_clean)} colunas total')
                self._log(f'Aba {aba} — {len(cols_clean)} colunas detectadas: {cols_clean}')
                
                # Atualiza combos de colunas e mostra o frame
                self.coluna_combo['values'] = cols_clean
                self.coluna_horario_combo['values'] = cols_clean
                self.coluna_var.set('')
                self.coluna_horario_var.set('')
                if cols_clean:
                    tipo = self.tipo_var.get()
                    nomes = ['Nome do Player', 'Player', 'Unidade', 'Nome'] if tipo == 'unidades' else \
                            ['Nome da Face', 'Face', 'Unidade', 'Tipo de Face', 'Nome']
                    self.coluna_var.set(self._achar_coluna(cols_clean, nomes) or cols_clean[0])
                    self.coluna_horario_var.set(
                        self._achar_coluna(cols_clean, [COLUNA_HORARIO, 'Horário', 'Horario']) or '')

                self.coluna_frame.pack(fill=tk.X, pady=(0, 15), after=self.aba_frame)
                self._atualizar_visibilidade_horario()

                # a linha inicial nunca pode ficar acima da 1ª linha de dados
                primeira_dado = self._linha_cabecalho + 1
                try:
                    if self.linha_var.get() < primeira_dado:
                        self.linha_var.set(primeira_dado)
                except tk.TclError:
                    self.linha_var.set(primeira_dado)

                self.coluna_info_var.set(
                    f'Cabeçalho na linha {self._linha_cabecalho} — dados começam na linha {primeira_dado}')
                self._ajustar_tamanho()
            except Exception as e:
                self.aba_info_var.set(f'Erro ao ler aba: {e}')
                self._log(f'[ERRO] Erro ao ler colunas: {e}')
                self.coluna_frame.pack_forget()

    @staticmethod
    def _achar_coluna(colunas, candidatas):
        """Acha a coluna ignorando maiúsculas/minúsculas e acentos."""
        import unicodedata

        def k(t):
            t = unicodedata.normalize('NFKD', str(t))
            return ''.join(c for c in t if not unicodedata.combining(c)).strip().casefold()

        mapa = {k(c): c for c in colunas}
        for cand in candidatas:
            if k(cand) in mapa:
                return mapa[k(cand)]
        return None

    def _atualizar_visibilidade_horario(self):
        tipo = self.tipo_var.get()
        if tipo in ('faces', 'panvel'):
            self.horario_row.pack_forget()
        else:
            self.horario_row.pack(fill=tk.X, pady=(8, 0))
        self._ajustar_tamanho()

    def _atualizar_visibilidade_anunciantes(self):
        tipo = self.tipo_var.get()
        if tipo in ('faces', 'ambos'):
            self.anunciantes_frame.pack(fill=tk.X, pady=(0, 15))
        else:
            self.anunciantes_frame.pack_forget()
        self._ajustar_tamanho()

    def _on_tipo_change(self):
        self._atualizar_visibilidade_horario()
        self._atualizar_visibilidade_anunciantes()
        tipo = self.tipo_var.get()
        if tipo == 'unidades':
            self._log('Modo: Unidades — Usa as colunas de nome e de horário escolhidas acima')
        elif tipo == 'faces':
            self._log('Modo: Faces — Usa coluna Nome da Face (ou Unidade, Face, Tipo de Face)')
        elif tipo == 'ambos':
            self._log('Modo: Ambos — Executa Unidades (Horários) e em seguida Faces (Anunciantes)')
        elif tipo == 'panvel':
            self._log('Modo: Panvel — Criação de Unidade Panvel (Aba 1 a 4 + Salvar)')

    def _confirmar(self):
        arquivo = self.arquivo_var.get().strip()
        if not arquivo:
            messagebox.showerror('Erro', 'Selecione um arquivo Excel.')
            return
        if not Path(arquivo).exists():
            messagebox.showerror('Erro', 'Arquivo não encontrado.')
            return
        aba = self.aba_var.get()
        if not aba:
            messagebox.showerror('Erro', 'Selecione uma aba da planilha.')
            return
        try:
            linha = self.linha_var.get()
        except tk.TclError:
            messagebox.showerror('Erro', 'Linha inicial inválida. Digite um número inteiro.')
            return
        if linha < 1:
            messagebox.showerror('Erro', 'Linha inicial deve ser ≥ 1.')
            return
        coluna = self.coluna_var.get()
        if not coluna:
            messagebox.showerror('Erro', 'Selecione uma coluna para busca.')
            return
        coluna_horario = self.coluna_horario_var.get()
        if self.tipo_var.get() not in ('faces', 'panvel') and not coluna_horario:
            messagebox.showerror('Erro', 'Selecione a coluna do Horário de funcionamento.')
            return
        email = self.email_var.get().strip()
        senha = self.senha_var.get()
        if not email or not senha:
            messagebox.showerror('Erro', 'Preencha e-mail e senha do Invian.')
            return
        valor_anunciantes = self.anunciantes_var.get() if self.tipo_var.get() in ('faces', 'ambos') else None
        self.result = {
            'tipo': self.tipo_var.get(),
            'arquivo': arquivo,
            'aba': aba,
            'linha_inicial': linha,
            'headless': self.headless_var.get(),
            'coluna': coluna,
            'coluna_horario': coluna_horario or None,
            'linha_cabecalho': getattr(self, '_linha_cabecalho', 1),
            'valor_anunciantes': valor_anunciantes,
            'email': email,
            'senha': senha,
        }
        self._log('[OK] Configuração válida. Iniciando...')
        self.root.destroy()

    def _cancelar(self):
        self.result = None
        self.root.destroy()

    def show(self):
        self.root.mainloop()
        return self.result

def abrir_configuracao():
    dialog = ConfigDialog()
    return dialog.show()
