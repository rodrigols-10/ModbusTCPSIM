# ui_manager.py

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
import threading
import time

from server_manager import ServerData

def safe_get_int(value, default=0):
    """Converte string em inteiro, se não for possível, retorna default."""
    try:
        return int(value)
    except ValueError:
        return default

class ModbusApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simulador de Servidores Modbus")
        self.iconbitmap("Resources/icon.ico")
        self.geometry("900x600")

        # Variáveis de configuração
        self.base_port = tk.IntVar(value=502)
        self.num_servers = tk.IntVar(value=1)
        self.num_coils = tk.IntVar(value=10)
        self.num_registers = tk.IntVar(value=10)

        # Lista de servidores
        self.servers_list = []
        self.running = False

        # Thread de atualização
        self.update_thread = None

        # ------ Random ------
        self.random_interval_ms = tk.IntVar(value=1000)
        self.random_active = False
        self.random_thread = None

        # ------ Simulação ------
        self.sim_tab_id = None     # Frame da aba "Simulação"
        self.sim_data = []         # Itens de simulação
        self.sim_thread = None
        self.sim_running = False

        # ------ Condição ------
        self.sim_condition = None  # dict ou None
        # Queremos reservar um espaço para exibir a condição, mas com altura=0 por padrão.
        # Então teremos um Frame (label_frame) e um Label, que inicia vazio.
        self.label_frame = None
        self.condition_label = None

        self._create_widgets()

    def _create_widgets(self):
        """Cria os widgets de configuração e o Notebook."""
        config_frame = ttk.LabelFrame(self, text="Configurações")
        config_frame.pack(fill="x", padx=5, pady=5)

        # Porta base
        ttk.Label(config_frame, text="Porta base:").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        tk.Entry(config_frame, textvariable=self.base_port, width=8).grid(row=0, column=1, padx=5, pady=2)

        # Nº de Servidores
        ttk.Label(config_frame, text="Nº de Servidores:").grid(row=0, column=2, padx=5, pady=2, sticky="e")
        tk.Entry(config_frame, textvariable=self.num_servers, width=8).grid(row=0, column=3, padx=5, pady=2)

        # Coils
        ttk.Label(config_frame, text="Coils:").grid(row=1, column=0, padx=5, pady=2, sticky="e")
        tk.Entry(config_frame, textvariable=self.num_coils, width=8).grid(row=1, column=1, padx=5, pady=2)

        # Registers
        ttk.Label(config_frame, text="Registers:").grid(row=1, column=2, padx=5, pady=2, sticky="e")
        tk.Entry(config_frame, textvariable=self.num_registers, width=8).grid(row=1, column=3, padx=5, pady=2)

        # Botões Start/Stop + CSV
        btn_frame = ttk.Frame(config_frame)
        btn_frame.grid(row=2, column=0, columnspan=4, pady=5)

        ttk.Button(btn_frame, text="Start", command=self.start_servers).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Stop", command=self.stop_servers).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Salvar CSV", command=self.save_servers_csv).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Importar CSV", command=self.import_servers_csv).pack(side="left", padx=5)

        # Random
        random_frame = ttk.Frame(config_frame)
        random_frame.grid(row=2, column=6, columnspan=4, pady=5, sticky="ew")
        ttk.Label(random_frame, text="Intervalo aleatório (ms):").pack(side="left", padx=5)
        self.interval_entry = tk.Entry(random_frame, textvariable=self.random_interval_ms, width=8, state="disabled")
        self.interval_entry.pack(side="left", padx=5)

        self.btn_random = ttk.Button(random_frame, text="Aleatório", command=self.toggle_random)
        self.btn_random.pack(side="left", padx=5)
        self.btn_random.configure(state="disabled")

        # Simular
        self.btn_simular = ttk.Button(config_frame, text="Simular", command=self.create_sim_tab)
        self.btn_simular.grid(row=2, column=5, padx=5, pady=5)
        self.btn_simular.configure(state="disabled")

        # Notebook principal
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

    # ------------------------------------------------------
    #               START / STOP Servidores
    # ------------------------------------------------------
    def start_servers(self):
        if self.running:
            messagebox.showinfo("Info", "Servidores já estão em execução.")
            return

        self.stop_servers()

        base_port = self.base_port.get()
        n_srv = self.num_servers.get()
        c = self.num_coils.get()
        r = self.num_registers.get()

        self.servers_list = []
        for i in range(n_srv):
            port = base_port + i
            srv = ServerData(port, c, r)
            try:
                srv.start()
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível iniciar servidor na porta {port}: {e}")
                continue
            self.servers_list.append(srv)
            self._create_server_tab(srv)

        if self.servers_list:
            self.running = True
            # Habilitar Random
            self.btn_random.configure(state="normal")
            self.interval_entry.configure(state="normal")
            # Habilitar Simular
            self.btn_simular.configure(state="normal")

            # Thread de atualização
            self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
            self.update_thread.start()

    def stop_servers(self):
        self.running = False
        # Parar random se estiver ativo
        if self.random_active:
            self.toggle_random()

        # Parar simulação
        if self.sim_running:
            self.stop_simulation()

        for srv in self.servers_list:
            srv.stop()
        self.servers_list.clear()

        # Remove todas as abas
        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)

        self.sim_tab_id = None
        self.sim_condition = None
        self.label_frame = None
        self.condition_label = None

        self.btn_random.configure(state="disabled")
        self.interval_entry.configure(state="disabled")
        self.btn_simular.configure(state="disabled")

    def _create_server_tab(self, srv: ServerData):
        """Cria uma aba para o servidor."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=f"Porta {srv.port}")

        columns = ("address", "type", "write_val", "read_val")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=15)
        tree.heading("address", text="Endereço")
        tree.heading("type", text="Tipo")
        tree.heading("write_val", text="Valor (Edição)")
        tree.heading("read_val", text="Valor (Leitura)")
        tree.column("address", width=80, anchor="center")
        tree.column("type", width=100, anchor="center")
        tree.column("write_val", width=120, anchor="center")
        tree.column("read_val", width=120, anchor="center")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        tree.pack(side="left", fill="both", expand=True)

        # Preenche coils
        for i in range(srv.num_coils):
            tree.insert("", "end", values=(i, "Coil", srv.coils[i], srv.coils[i]))
        # Preenche registers
        for i in range(srv.num_registers):
            tree.insert("", "end", values=(i, "Register", srv.registers[i], srv.registers[i]))

        tree.bind("<Double-1>", lambda e, t=tree, s=srv: self._on_edit_cell(e, t, s))

    def _on_edit_cell(self, event, tree, srv: ServerData):
        """Edição do valor (coluna 'Valor (Edição)') via duplo clique."""
        item_id = tree.identify_row(event.y)
        col = tree.identify_column(event.x)
        if not item_id or col != "#3":
            return

        vals = list(tree.item(item_id, "values"))  # [address, type, write_val, read_val]
        address = safe_get_int(vals[0])
        type_ = vals[1]

        x, y, w, h = tree.bbox(item_id, col)
        edit_win = tk.Toplevel(self)
        edit_win.overrideredirect(True)
        edit_win.geometry(f"{w}x{h}+{tree.winfo_rootx()+x}+{tree.winfo_rooty()+y}")

        var_str = tk.StringVar(value=str(vals[2]))
        entry = tk.Entry(edit_win, textvariable=var_str)
        entry.pack(fill="both", expand=True)
        entry.focus()

        def on_commit(_):
            new_val = safe_get_int(var_str.get())
            if type_ == "Coil":
                srv.update_coil(address, new_val)
            else:
                srv.update_register(address, new_val)
            vals[2] = new_val
            tree.item(item_id, values=vals)
            edit_win.destroy()

        entry.bind("<Return>", on_commit)
        entry.bind("<FocusOut>", on_commit)
        entry.bind("<Escape>", lambda e: edit_win.destroy())

    def update_loop(self):
        """Thread de polling para atualizar a exibição (coluna 'Valor (Leitura)')."""
        while self.running:
            for idx, srv in enumerate(self.servers_list):
                srv.read_all()
                if idx >= len(self.notebook.tabs()):
                    continue
                tab_id = self.notebook.tabs()[idx]
                frame = self.notebook.nametowidget(tab_id)

                tree = None
                for w in frame.winfo_children():
                    if isinstance(w, ttk.Treeview):
                        tree = w
                        break
                if not tree:
                    continue
                items = tree.get_children()

                # Coils
                for i in range(srv.num_coils):
                    item_id = items[i]
                    row_vals = list(tree.item(item_id, "values"))
                    row_vals[3] = srv.coils[i]  # read_val
                    tree.item(item_id, values=row_vals)

                # Registers
                offset = srv.num_coils
                for i in range(srv.num_registers):
                    item_id = items[offset + i]
                    row_vals = list(tree.item(item_id, "values"))
                    row_vals[3] = srv.registers[i]
                    tree.item(item_id, values=row_vals)

            time.sleep(0.5)

    # ------------------------------------------------------
    #            SAVE/IMPORT CSV de Servidores
    # ------------------------------------------------------
    def save_servers_csv(self):
        if not self.servers_list:
            messagebox.showinfo("Info", "Nenhum servidor para salvar.")
            return
        fp = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not fp:
            return
        with open(fp, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["Port", "Type", "Address", "Value"])
            for srv in self.servers_list:
                for i, val in enumerate(srv.coils):
                    w.writerow([srv.port, "Coil", i, val])
                for i, val in enumerate(srv.registers):
                    w.writerow([srv.port, "Register", i, val])
        messagebox.showinfo("Sucesso", f"Salvo em {fp}")

    def import_servers_csv(self):
        fp = filedialog.askopenfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not fp:
            return
        data_dict = {}
        try:
            with open(fp, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    p = safe_get_int(row["Port"])
                    t = row["Type"]
                    a = safe_get_int(row["Address"])
                    v = safe_get_int(row["Value"])
                    if p not in data_dict:
                        data_dict[p] = {"max_coil": -1, "max_reg": -1, "coils": {}, "regs": {}}
                    if t == "Coil":
                        data_dict[p]["coils"][a] = v
                        if a > data_dict[p]["max_coil"]:
                            data_dict[p]["max_coil"] = a
                    else:
                        data_dict[p]["regs"][a] = v
                        if a > data_dict[p]["max_reg"]:
                            data_dict[p]["max_reg"] = a
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao ler CSV: {e}")
            return

        self.stop_servers()
        for port, info in data_dict.items():
            c_count = info["max_coil"] + 1 if info["max_coil"] >= 0 else 0
            r_count = info["max_reg"] + 1 if info["max_reg"] >= 0 else 0
            srv = ServerData(port, c_count, r_count)
            for k, val in info["coils"].items():
                srv.coils[k] = 1 if val != 0 else 0
            for k, val in info["regs"].items():
                srv.registers[k] = val
            try:
                srv.start()
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível iniciar servidor na porta {port}: {e}")
                continue
            self.servers_list.append(srv)
            self._create_server_tab(srv)

        if self.servers_list:
            self.running = True
            self.btn_random.configure(state="normal")
            self.interval_entry.configure(state="normal")
            self.btn_simular.configure(state="normal")

            self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
            self.update_thread.start()

    # ------------------------------------------------------
    #                   Geração Random
    # ------------------------------------------------------
    def toggle_random(self):
        if not self.servers_list:
            return
        if not self.random_active:
            # Iniciar random
            self.random_active = True
            self.btn_random.config(text="Parar Aleatório")
            interval = self.random_interval_ms.get()
            self.random_thread = threading.Thread(target=self._random_loop, args=(interval,), daemon=True)
            self.random_thread.start()
        else:
            # Parar
            self.random_active = False
            self.btn_random.config(text="Aleatório")
            # Zera todos
            for srv in self.servers_list:
                srv.set_all_zero()

    def _random_loop(self, interval_ms):
        while self.random_active:
            for srv in self.servers_list:
                srv.set_random_values()
            time.sleep(interval_ms / 1000.0)

    # ------------------------------------------------------
    #                    Simulação
    # ------------------------------------------------------
    def create_sim_tab(self):
        """Cria a aba de simulação (ou seleciona se já existe)."""
        if self.sim_tab_id is not None:
            self.notebook.select(self.sim_tab_id)
            return

        sim_frame = ttk.Frame(self.notebook)
        self.sim_tab_id = sim_frame
        self.notebook.add(sim_frame, text="Simulação")
        self.notebook.select(sim_frame)

        # ---------- BARRA DE BOTÕES ----------
        top_frame = ttk.Frame(sim_frame)
        top_frame.pack(fill="x", padx=5, pady=5)

        ttk.Button(top_frame, text="Adicionar", command=self.add_sim_point).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Remover", command=self.remove_sim_point).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Executar", command=self.execute_simulation).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Parar", command=self.stop_simulation).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Salvar CSV", command=self.save_sim_csv).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Importar CSV", command=self.import_sim_csv).pack(side="left", padx=5)

        # Botão de condição (Adicionar/Remover)
        self.btn_condition = ttk.Button(top_frame, text="Adicionar Condição", command=self.toggle_condition)
        self.btn_condition.pack(side="left", padx=5)

        # ---------- FRAME PARA A CONDIÇÃO ----------
        # Espaço reservado, altura=0 enquanto não há condição
        self.label_frame = ttk.Frame(sim_frame)
        self.label_frame.pack(fill="x", padx=5, pady=(0,5))  # top=0, bottom=5
        self.label_frame.pack_propagate(False)  # Não se ajusta automaticamente ao conteúdo
        self.label_frame.configure(height=30)    # começa sem altura

        # O label em si (inicia vazio)
        self.condition_label = tk.Label(self.label_frame, text="Execução sem condição (início imediato)", fg="blue")
        self.condition_label.pack()

        # ---------- TABELA (TreeView) ----------
        columns = ("server_port", "type", "address", "value", "time_ms")
        self.sim_tree = ttk.Treeview(sim_frame, columns=columns, show="headings", height=10)
        self.sim_tree.heading("server_port", text="Servidor (Port)")
        self.sim_tree.heading("type", text="Tipo")
        self.sim_tree.heading("address", text="Endereço")
        self.sim_tree.heading("value", text="Valor")
        self.sim_tree.heading("time_ms", text="Tempo (ms)")

        for col in columns:
            self.sim_tree.column(col, anchor="center", width=100)

        vsb = ttk.Scrollbar(sim_frame, orient="vertical", command=self.sim_tree.yview)
        self.sim_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        self.sim_tree.pack(side="left", fill="both", expand=True)

    def add_sim_point(self):
        if not self.servers_list:
            return
        win = tk.Toplevel(self)
        win.title("Adicionar Ponto")

        tk.Label(win, text="Servidor (Port):").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        sv_var = tk.IntVar(value=self.servers_list[0].port)
        ttk.Combobox(win, textvariable=sv_var, values=[s.port for s in self.servers_list]).grid(row=0, column=1, padx=5, pady=5)

        tk.Label(win, text="Tipo (Coil/Register):").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        tp_var = tk.StringVar(value="Coil")
        ttk.Combobox(win, textvariable=tp_var, values=["Coil","Register"], state="readonly").grid(row=1, column=1, padx=5, pady=5)

        tk.Label(win, text="Endereço:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        ad_var = tk.StringVar(value="0")
        tk.Entry(win, textvariable=ad_var).grid(row=2, column=1, padx=5, pady=5)

        tk.Label(win, text="Valor:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        vl_var = tk.StringVar(value="1")
        tk.Entry(win, textvariable=vl_var).grid(row=3, column=1, padx=5, pady=5)

        tk.Label(win, text="Tempo (ms):").grid(row=4, column=0, sticky="e", padx=5, pady=5)
        tm_var = tk.StringVar(value="1000")
        tk.Entry(win, textvariable=tm_var).grid(row=4, column=1, padx=5, pady=5)

        def on_ok():
            port = safe_get_int(sv_var.get())
            t = tp_var.get()
            addr = safe_get_int(ad_var.get())
            val = safe_get_int(vl_var.get())
            ms = safe_get_int(tm_var.get())
            srv = self._find_server_by_port(port)
            if not srv:
                messagebox.showerror("Erro", f"Servidor na porta {port} não existe.")
                return
            if t == "Coil" and (addr<0 or addr>=srv.num_coils):
                messagebox.showerror("Erro", f"Endereço coil inválido (0..{srv.num_coils-1})")
                return
            if t == "Register" and (addr<0 or addr>=srv.num_registers):
                messagebox.showerror("Erro", f"Endereço register inválido (0..{srv.num_registers-1})")
                return

            self.sim_tree.insert("", "end", values=(port, t, addr, val, ms))
            win.destroy()

        tk.Button(win, text="OK", command=on_ok).grid(row=5, column=0, columnspan=2, pady=10)

    def remove_sim_point(self):
        sel = self.sim_tree.selection()
        for it in sel:
            self.sim_tree.delete(it)

    def execute_simulation(self):
        if self.sim_running:
            messagebox.showinfo("Info", "Simulação já está em execução.")
            return
        items = self.sim_tree.get_children()
        self.sim_data = []
        for it in items:
            vals = self.sim_tree.item(it, "values")
            self.sim_data.append({
                "port": safe_get_int(vals[0]),
                "type": vals[1],
                "address": safe_get_int(vals[2]),
                "value": safe_get_int(vals[3]),
                "time_ms": safe_get_int(vals[4]),
            })
        self.sim_data.sort(key=lambda x: x["time_ms"])
        self.sim_running = True
        self.sim_thread = threading.Thread(target=self._sim_loop, daemon=True)
        self.sim_thread.start()

    def _sim_loop(self):
        # 1) Se houver condição, aguardar até ser satisfeita
        if self.sim_condition:
            while self.sim_running and not self._condition_satisfied():
                time.sleep(0.1)

        # 2) Executar os eventos
        start_time = time.time() * 1000
        idx = 0
        while self.sim_running and idx < len(self.sim_data):
            current_ms = time.time()*1000 - start_time
            if current_ms >= self.sim_data[idx]["time_ms"]:
                d = self.sim_data[idx]
                srv = self._find_server_by_port(d["port"])
                if srv:
                    if d["type"] == "Coil":
                        srv.update_coil(d["address"], d["value"])
                    else:
                        srv.update_register(d["address"], d["value"])
                idx += 1
            else:
                time.sleep(0.02)

        self.sim_running = False

    def stop_simulation(self):
        self.sim_running = False

    def _find_server_by_port(self, port):
        for s in self.servers_list:
            if s.port == port:
                return s
        return None

    # --------------- CSV da SIMULAÇÃO ---------------
    def save_sim_csv(self):
        if not self.sim_tree or not self.sim_tab_id:
            return
        fp = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files","*.csv")])
        if not fp:
            return
        with open(fp, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["Port","Type","Address","Value","Time_ms"])
            for it in self.sim_tree.get_children():
                vals = self.sim_tree.item(it,"values")
                w.writerow(vals)
        messagebox.showinfo("Sucesso", f"Simulação salva em {fp}")

    def import_sim_csv(self):
        if not self.servers_list:
            messagebox.showinfo("Info","Não há servidores em execução.")
            return
        fp = filedialog.askopenfilename(defaultextension=".csv", filetypes=[("CSV Files","*.csv")])
        if not fp:
            return
        try:
            with open(fp,"r",encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    port = safe_get_int(row["Port"])
                    t = row["Type"]
                    addr = safe_get_int(row["Address"])
                    val = safe_get_int(row["Value"])
                    ms = safe_get_int(row["Time_ms"])
                    srv = self._find_server_by_port(port)
                    if not srv:
                        continue
                    if t=="Coil" and addr>=srv.num_coils:
                        continue
                    if t=="Register" and addr>=srv.num_registers:
                        continue
                    self.sim_tree.insert("", "end", values=(port,t,addr,val,ms))
        except Exception as e:
            messagebox.showerror("Erro",f"Falha ao importar simulação: {e}")

    # ------------------------------------------------------
    #            CONDIÇÃO (Adicionar/Remover)
    # ------------------------------------------------------
    def toggle_condition(self):
        """Alterna entre adicionar e remover condição."""
        if self.sim_condition:
            # Remover
            self.sim_condition = None
            self.btn_condition.config(text="Adicionar Condição")
            # Zera o texto e altura do label_frame
            if self.condition_label:
                self.condition_label.config(text="Execução sem condição (início imediato)")
           # if self.label_frame:
                #self.label_frame.configure(height=30)
            messagebox.showinfo("Info", "Condição removida!")
        else:
            # Adicionar
            self.add_condition()

    def add_condition(self):
        """Abre janela para definir a condição."""
        if not self.servers_list:
            return
        win = tk.Toplevel(self)
        win.title("Adicionar Condição")

        tk.Label(win, text="Servidor (Port):").grid(row=0,column=0,padx=5,pady=5,sticky="e")
        sv_var = tk.IntVar(value=self.servers_list[0].port)
        ttk.Combobox(win, textvariable=sv_var, values=[s.port for s in self.servers_list]).grid(row=0,column=1,padx=5,pady=5)

        tk.Label(win, text="Tipo (Coil/Register):").grid(row=1,column=0,padx=5,pady=5,sticky="e")
        tp_var = tk.StringVar(value="Coil")
        ttk.Combobox(win,textvariable=tp_var,values=["Coil","Register"],state="readonly").grid(row=1,column=1,padx=5,pady=5)

        tk.Label(win, text="Endereço:").grid(row=2,column=0,padx=5,pady=5,sticky="e")
        ad_var = tk.StringVar(value="0")
        tk.Entry(win,textvariable=ad_var).grid(row=2,column=1,padx=5,pady=5)

        tk.Label(win, text="Operador (=,>,<):").grid(row=3,column=0,padx=5,pady=5,sticky="e")
        op_var = tk.StringVar(value="=")
        ttk.Combobox(win, textvariable=op_var, values=["=",">","<"], state="readonly").grid(row=3,column=1,padx=5,pady=5)

        tk.Label(win, text="Valor:").grid(row=4,column=0,padx=5,pady=5,sticky="e")
        val_var = tk.StringVar(value="1")
        tk.Entry(win, textvariable=val_var).grid(row=4,column=1,padx=5,pady=5)

        def on_ok():
            p = safe_get_int(sv_var.get())
            t = tp_var.get()
            a = safe_get_int(ad_var.get())
            o = op_var.get()
            v = safe_get_int(val_var.get())
            srv = self._find_server_by_port(p)
            if not srv:
                messagebox.showerror("Erro", f"Servidor {p} não existe.")
                return
            if t=="Coil" and (a<0 or a>=srv.num_coils):
                messagebox.showerror("Erro", f"Coil inválido: 0..{srv.num_coils-1}")
                return
            if t=="Register" and (a<0 or a>=srv.num_registers):
                messagebox.showerror("Erro", f"Register inválido: 0..{srv.num_registers-1}")
                return
            if o not in ["=",">","<"]:
                messagebox.showerror("Erro", "Operador inválido.")
                return

            self.sim_condition = {"port":p,"type":t,"address":a,"operator":o,"value":v}
            self.btn_condition.config(text="Remover Condição")

            # Formata texto e exibe no label
            cond_str = self._format_condition_text(self.sim_condition)
            self.condition_label.config(text=cond_str)
            # Ajusta a altura do frame
            self.label_frame.configure(height=30)

            messagebox.showinfo("Info", "Condição adicionada com sucesso!")
            win.destroy()

        tk.Button(win, text="OK", command=on_ok).grid(row=5, column=0, columnspan=2, pady=10)

    def _format_condition_text(self, cond):
        """Retorna string para exibir a condição."""
        return (f"Execução pela condição: Servidor={cond['port']} "
                f"({cond['type']}[{cond['address']}]) "
                f"{cond['operator']} {cond['value']}")

    def _condition_satisfied(self):
        if not self.sim_condition:
            return True
        c = self.sim_condition
        srv = self._find_server_by_port(c["port"])
        if not srv:
            return False
        srv.read_all()
        if c["type"]=="Coil":
            val = srv.coils[c["address"]]
        else:
            val = srv.registers[c["address"]]

        if c["operator"]=="=":
            return val == c["value"]
        elif c["operator"]==">":
            return val > c["value"]
        elif c["operator"]=="<":
            return val < c["value"]
        return False
