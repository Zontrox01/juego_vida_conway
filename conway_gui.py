import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import csv
import threading
import time
from PIL import Image, ImageDraw
import sys
import os
import random
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Las clases se definen aquí (en lugar de importarlas de main.py)
# para evitar que se ejecute el código principal de main.py.

# Nombres visibles de los modos de contorno (los valores internos no cambian
# para que los CSV guardados anteriormente sigan funcionando).
MODOS_TEXTO = {"normal": "Normal", "periodic": "Periódico", "mirror": "Espejo"}


# ---------------------------------------------------------------------------
# REGLAS CONFIGURABLES
# ---------------------------------------------------------------------------
def _lista_texto(valores):
    """Convierte {2, 3, 5} en '2, 3 o 5'."""
    v = sorted(valores)
    if len(v) == 1:
        return str(v[0])
    return ", ".join(str(x) for x in v[:-1]) + " o " + str(v[-1])


class Reglas:
    """Todos los parámetros que gobiernan nacimiento, supervivencia, cura y muerte.

    Los valores por defecto reproducen exactamente el comportamiento original.
    """

    DEFECTO = {
        # Nacimiento y supervivencia de células vivas (nº de vecinas vivas)
        "nacimiento": frozenset({3}),
        "supervivencia": frozenset({2, 3}),
        "viva_muere_cancer_min": 0,        # 0 = desactivado (no existía antes)
        # Nacimiento de cáncer en una célula muerta
        "cancer_nace_min": 1,              # vecinas de cáncer mínimas
        "cancer_nace_prob": 0.1,           # probabilidad base
        "cancer_nace_peso_ref": 0.01,      # peso de referencia
        # Nacimiento de cura en una célula muerta
        "cura_nace_min": 5,
        "cura_nace_prob": 0.5,
        "cura_nace_peso_ref": 0.1,
        "cura_peso_defecto": 0.1,          # peso si no hay cura cerca
        # Cáncer curado por la cura (pasa a célula viva)
        "cancer_curado_min": 1,
        "cancer_curado_prob": 0.5,
        "cancer_curado_peso_ref": 0.1,
        "cancer_resistencia": 0.1,
        "cancer_resistencia_peso_ref": 0.01,
        "cancer_curado_prob_min": 0.3,
        # Muerte del cáncer por sobrepoblación
        "cancer_satura_base": 7,
        "cancer_satura_min": 5,
        "cancer_satura_peso_ref": 0.01,
        # Muerte de la cura por aislamiento (demasiadas vecinas muertas)
        "cura_aislada_base": 6,
        "cura_aislada_min": 4,
        "cura_aislada_peso_ref": 0.1,
        # Muerte de la cura por sobrepoblación (demasiadas vecinas de cura)
        "cura_satura_base": 3,
        "cura_satura_min": 2,
        "cura_satura_peso_ref": 0.1,
    }

    GRUPOS = {
        "nacimiento": ["nacimiento", "cancer_nace_min", "cancer_nace_prob", "cancer_nace_peso_ref",
                       "cura_nace_min", "cura_nace_prob", "cura_nace_peso_ref"],
        "supervivencia": ["supervivencia", "viva_muere_cancer_min"],
        "cancer": ["cancer_curado_min", "cancer_curado_prob", "cancer_curado_peso_ref",
                   "cancer_resistencia", "cancer_resistencia_peso_ref", "cancer_curado_prob_min",
                   "cancer_satura_base", "cancer_satura_min", "cancer_satura_peso_ref"],
        "cura": ["cura_peso_defecto", "cura_aislada_base", "cura_aislada_min", "cura_aislada_peso_ref",
                 "cura_satura_base", "cura_satura_min", "cura_satura_peso_ref"],
    }

    def __init__(self):
        self.restaurar()

    # --- acceso ---------------------------------------------------------
    def obtener(self, clave):
        return getattr(self, clave)

    def poner(self, clave, valor):
        if clave in ("nacimiento", "supervivencia"):
            valor = frozenset(int(v) for v in valor if 0 <= int(v) <= 8)
        setattr(self, clave, valor)

    def restaurar(self, claves=None):
        """Vuelve a los valores por defecto (todos, o solo las claves indicadas)."""
        for clave in (claves or self.DEFECTO.keys()):
            setattr(self, clave, self.DEFECTO[clave])

    # --- fórmulas (las usan las células y la interfaz) --------------------
    def prob_cancer_nace(self, peso_medio):
        return min(1.0, self.cancer_nace_prob * (peso_medio / self.cancer_nace_peso_ref))

    def prob_cura_nace(self, peso_medio):
        return min(1.0, self.cura_nace_prob * (peso_medio / self.cura_nace_peso_ref))

    def prob_cancer_curado(self, peso_cura, peso_cancer):
        fuerza = (peso_cura / self.cancer_curado_peso_ref) * self.cancer_curado_prob
        resistencia = (peso_cancer / self.cancer_resistencia_peso_ref) * self.cancer_resistencia
        return max(self.cancer_curado_prob_min, fuerza - resistencia)

    def umbral_cancer_satura(self, peso):
        modificador = (peso / self.cancer_satura_peso_ref) - 1
        return max(self.cancer_satura_min, int(self.cancer_satura_base - modificador))

    def umbral_cura_aislada(self, peso):
        modificador = (peso / self.cura_aislada_peso_ref) - 1
        return max(self.cura_aislada_min, int(self.cura_aislada_base + modificador))

    def umbral_cura_satura(self, peso):
        modificador = (peso / self.cura_satura_peso_ref) - 1
        return max(self.cura_satura_min, int(self.cura_satura_base + modificador))

    # --- notación y explicaciones -------------------------------------
    def notacion(self):
        """Notación N/S (Nacimiento/Supervivencia), por ejemplo N3/S23."""
        b = "".join(str(n) for n in sorted(self.nacimiento))
        s = "".join(str(n) for n in sorted(self.supervivencia))
        return f"N{b}/S{s}"

    def textos(self, peso_cancer=0.01, peso_cura=0.1):
        """Explicaciones en español, con la matemática de la configuración actual."""
        if self.nacimiento:
            plural = "vecina viva" if self.nacimiento == {1} else "vecinas vivas"
            nac = (f"Nacimiento: una célula muerta nace (pasa a viva) si tiene "
                   f"{_lista_texto(self.nacimiento)} {plural}.  "
                   f"Matemáticamente: nace si N ∈ {{{', '.join(map(str, sorted(self.nacimiento)))}}}, "
                   f"siendo N el nº de vecinas vivas (de las 8 que la rodean).")
        else:
            nac = "Nacimiento: una célula muerta nunca pasa a viva."

        if self.supervivencia:
            plural = "vecina viva" if self.supervivencia == {1} else "vecinas vivas"
            sup = (f"Supervivencia: una célula viva sigue viva si tiene "
                   f"{_lista_texto(self.supervivencia)} {plural}; en otro caso muere "
                   f"(por soledad o sobrepoblación).  "
                   f"Matemáticamente: sobrevive si N ∈ {{{', '.join(map(str, sorted(self.supervivencia)))}}}.")
        else:
            sup = "Supervivencia: ninguna célula viva sobrevive; todas mueren en la siguiente generación."

        if self.viva_muere_cancer_min > 0:
            viva_cancer = (f"Además, una célula viva muere si tiene ≥ {self.viva_muere_cancer_min} "
                           f"vecinas de cáncer.")
        else:
            viva_cancer = "El cáncer no mata directamente a las células vivas (desactivado)."

        return {
            "nacimiento": nac,
            "supervivencia": sup,
            "viva_muere_cancer": viva_cancer,
            "cancer_nace": (f"Si una célula muerta tiene ≥ {self.cancer_nace_min} vecinas de cáncer:  "
                            f"P(nace cáncer) = mín(1; {self.cancer_nace_prob:g} × peso medio del cáncer vecino "
                            f"/ {self.cancer_nace_peso_ref:g}).  "
                            f"Con peso {peso_cancer:g}: P = {self.prob_cancer_nace(peso_cancer):.1%}"),
            "cura_nace": (f"Si una célula muerta tiene ≥ {self.cura_nace_min} vecinas de cáncer:  "
                          f"P(nace cura) = mín(1; {self.cura_nace_prob:g} × peso medio de la cura vecina "
                          f"/ {self.cura_nace_peso_ref:g})  "
                          f"(sin cura vecina se usa el peso {self.cura_peso_defecto:g}).  "
                          f"Con peso {peso_cura:g}: P = {self.prob_cura_nace(peso_cura):.1%}"),
            "cancer_curado": (f"Si una célula de cáncer tiene ≥ {self.cancer_curado_min} vecinas de cura:  "
                              f"P(curarse y pasar a viva) = máx({self.cancer_curado_prob_min:g}; "
                              f"{self.cancer_curado_prob:g} × peso_cura / {self.cancer_curado_peso_ref:g} "
                              f"− {self.cancer_resistencia:g} × peso_cáncer / {self.cancer_resistencia_peso_ref:g}).  "
                              f"Con los pesos actuales: P = {self.prob_cancer_curado(peso_cura, peso_cancer):.1%}"),
            "cancer_satura": (f"El cáncer muere por sobrepoblación si tiene ≥ U vecinas de cáncer, con "
                              f"U = máx({self.cancer_satura_min}; {self.cancer_satura_base} − "
                              f"(peso / {self.cancer_satura_peso_ref:g} − 1)).  "
                              f"Con peso {peso_cancer:g}: U = {self.umbral_cancer_satura(peso_cancer)}"),
            "cura_aislada": (f"La cura muere por aislamiento si tiene ≥ U vecinas muertas, con "
                             f"U = máx({self.cura_aislada_min}; {self.cura_aislada_base} + "
                             f"(peso / {self.cura_aislada_peso_ref:g} − 1)).  "
                             f"Con peso {peso_cura:g}: U = {self.umbral_cura_aislada(peso_cura)}"),
            "cura_satura": (f"La cura muere por sobrepoblación si tiene ≥ U vecinas de cura, con "
                            f"U = máx({self.cura_satura_min}; {self.cura_satura_base} + "
                            f"(peso / {self.cura_satura_peso_ref:g} − 1)).  "
                            f"Con peso {peso_cura:g}: U = {self.umbral_cura_satura(peso_cura)}"),
        }

    # --- guardado y carga en CSV ------------------------------------------
    def a_filas(self):
        filas = [["rule_birth"] + sorted(self.nacimiento),
                 ["rule_survival"] + sorted(self.supervivencia)]
        for clave in self.DEFECTO:
            if clave not in ("nacimiento", "supervivencia"):
                filas.append(["rule_param", clave, self.obtener(clave)])
        return filas

    def cargar_fila(self, fila):
        """Procesa una fila de regla del CSV. Devuelve True si la fila era una regla."""
        try:
            if fila[0] == "rule_birth":
                self.poner("nacimiento", [int(x) for x in fila[1:] if x != ""])
                return True
            if fila[0] == "rule_survival":
                self.poner("supervivencia", [int(x) for x in fila[1:] if x != ""])
                return True
            if fila[0] == "rule_param":
                clave = fila[1]
                if clave in self.DEFECTO and clave not in ("nacimiento", "supervivencia"):
                    tipo = type(self.DEFECTO[clave])
                    self.poner(clave, tipo(float(fila[2])) if tipo is int else float(fila[2]))
                return True
        except (ValueError, IndexError):
            return True  # fila de regla dañada: se ignora
        return False


# Reglas globales usadas por todas las células
REGLAS = Reglas()


class Location:
    def __init__(self, i: int, j: int):
        self.i = i
        self.j = j

class ImplCell:
    def __init__(self, location, grid):
        self.location = location
        self.grid = grid

    def process(self):
        pass

    def clone(self, grid):
        pass

    def _peso_medio_vecinas(self, tipo, atributo):
        """Peso medio de las vecinas de un tipo (None si no hay ninguna)."""
        total = 0
        cantidad = 0
        for di in [-1, 0, 1]:
            for dj in [-1, 0, 1]:
                if di == 0 and dj == 0:
                    continue
                ni, nj = self.location.i + di, self.location.j + dj
                if 0 <= ni < self.grid.rows and 0 <= nj < self.grid.cols:
                    celula = self.grid.cells[ni][nj]
                    if isinstance(celula, tipo):
                        total += getattr(celula, atributo)
                        cantidad += 1
        return total / cantidad if cantidad > 0 else None

    def __str__(self):
        return " "

class DeadCell(ImplCell):
    def __init__(self, row, col, grid):
        super().__init__(Location(row, col), grid)

    def clone(self, grid):
        return DeadCell(self.location.i, self.location.j, grid)

    def process(self):
        r = REGLAS
        i, j = self.location.i, self.location.j

        # Regla de nacimiento (por defecto: exactamente 3 vecinas vivas)
        vecinas_vivas = self.grid.count_neighbors(i, j)
        if vecinas_vivas in r.nacimiento:
            return AliveCell(i, j, self.grid)

        # Propagación del cáncer: la probabilidad depende del peso medio
        vecinas_cancer = self.grid.count_neighbors(i, j, CancerCell)
        if vecinas_cancer >= r.cancer_nace_min:
            peso_medio = self._peso_medio_vecinas(CancerCell, "cancer_weighting")
            if peso_medio is not None:
                if random.random() < r.prob_cancer_nace(peso_medio):
                    nuevo = CancerCell(i, j, self.grid)
                    nuevo.cancer_weighting = peso_medio
                    return nuevo

        # Aparición de cura cuando hay mucho cáncer alrededor
        if vecinas_cancer >= r.cura_nace_min:
            peso_medio = self._peso_medio_vecinas(CureCell, "cure_weighting")
            if peso_medio is None:
                peso_medio = r.cura_peso_defecto
            if random.random() < r.prob_cura_nace(peso_medio):
                nueva = CureCell(i, j, self.grid)
                nueva.cure_weighting = peso_medio
                return nueva

        return DeadCell(i, j, self.grid)

    def __str__(self):
        return "🟥"

class AliveCell(ImplCell):
    def __init__(self, row, col, grid):
        super().__init__(Location(row, col), grid)

    def process(self):
        r = REGLAS
        i, j = self.location.i, self.location.j
        # Muerte opcional por contacto con cáncer (0 = desactivado)
        if r.viva_muere_cancer_min > 0:
            if self.grid.count_neighbors(i, j, CancerCell) >= r.viva_muere_cancer_min:
                return DeadCell(i, j, self.grid)
        # Regla de supervivencia (por defecto: 2 o 3 vecinas vivas)
        vecinas = self.grid.count_neighbors(i, j)
        if vecinas in r.supervivencia:
            return AliveCell(i, j, self.grid)
        return DeadCell(i, j, self.grid)

    def clone(self, grid):
        return AliveCell(self.location.i, self.location.j, grid)

    def __str__(self):
        return "🟩"

class CancerCell(ImplCell):
    def __init__(self, row, col, grid):
        self.cancer_weighting = 0.01
        super().__init__(Location(row, col), grid)

    def process(self):
        r = REGLAS
        loc = self.location
        vecinas_cura = self.grid.count_neighbors(loc.i, loc.j, CureCell)
        vecinas_cancer = self.grid.count_neighbors(loc.i, loc.j, CancerCell)

        # La cura intenta curar al cáncer (la célula pasa a ser una célula viva)
        if vecinas_cura >= r.cancer_curado_min:
            peso_cura = self._peso_medio_vecinas(CureCell, "cure_weighting")
            if peso_cura is None:
                peso_cura = r.cura_peso_defecto
            if random.random() < r.prob_cancer_curado(peso_cura, self.cancer_weighting):
                return AliveCell(loc.i, loc.j, self.grid)

        # Muerte por sobrepoblación: el umbral depende del peso
        if vecinas_cancer >= r.umbral_cancer_satura(self.cancer_weighting):
            return DeadCell(loc.i, loc.j, self.grid)

        # El cáncer persiste
        nuevo = CancerCell(loc.i, loc.j, self.grid)
        nuevo.cancer_weighting = self.cancer_weighting
        return nuevo

    def clone(self, grid):
        nuevo = CancerCell(self.location.i, self.location.j, grid)
        nuevo.cancer_weighting = self.cancer_weighting
        return nuevo

    def __str__(self):
        return "⬜"

class CureCell(ImplCell):
    def __init__(self, row, col, grid):
        self.cure_weighting = 0.1
        super().__init__(Location(row, col), grid)

    def process(self):
        r = REGLAS
        loc = self.location
        vecinas_cura = self.grid.count_neighbors(loc.i, loc.j, CureCell)
        vecinas_muertas = self.grid.count_neighbors(loc.i, loc.j, DeadCell)

        # Muerte por aislamiento
        if vecinas_muertas >= r.umbral_cura_aislada(self.cure_weighting):
            return DeadCell(loc.i, loc.j, self.grid)

        # Muerte por sobrepoblación
        if vecinas_cura >= r.umbral_cura_satura(self.cure_weighting):
            return DeadCell(loc.i, loc.j, self.grid)

        # La cura persiste
        nueva = CureCell(loc.i, loc.j, self.grid)
        nueva.cure_weighting = self.cure_weighting
        return nueva

    def __str__(self):
        return "🟦"

    def clone(self, grid):
        nueva = CureCell(self.location.i, self.location.j, grid)
        nueva.cure_weighting = self.cure_weighting
        return nueva

class Grid:
    def __init__(self, rows, cols, mode_list=None):
        self.rows = rows
        self.cols = cols
        # Lista nueva en cada cuadrícula (antes era un valor por defecto compartido)
        self.mode_list = list(mode_list) if mode_list is not None else ["normal", "normal", "normal", "normal"]
        self.cells = [[DeadCell(j, i, self) for i in range(cols)] for j in range(rows)]

    def set_cell(self, cell):
        self.cells[cell.location.i][cell.location.j] = cell

    def clone(self):
        new_grid = Grid(self.rows, self.cols, self.mode_list)
        for i in range(len(self.cells)):
            for j in range(len(self.cells[0])):
                new_grid.cells[i][j] = self.cells[i][j].clone(new_grid)
        return new_grid

    def get_cell(self, row, col):
        return self.cells[row][col]

    def check_left(self, col, mode="normal"):
        if mode == "periodic":
            return col % len(self.cells[0])
        elif mode == "mirror" and col < 0:
            return 0
        elif col < 0:
            return None
        return col

    def check_right(self, col, mode="normal"):
        if mode == "periodic":
            return col % len(self.cells[0])
        elif mode == "mirror" and col > len(self.cells[0]) - 1:
            return len(self.cells[0]) - 1
        elif col > len(self.cells[0]) - 1:
            return None
        return col

    def check_up(self, row, mode="normal"):
        if mode == "periodic":
            return row % len(self.cells)
        elif mode == "mirror" and row < 0:
            return 0
        elif row < 0:
            return None
        return row

    def check_down(self, row, mode="normal"):
        if mode == "periodic":
            return row % len(self.cells)
        elif mode == "mirror" and row > len(self.cells) - 1:
            return len(self.cells) - 1
        elif row > len(self.cells) - 1:
            return None
        return row

    def row_processor(self, row, i, mode_list):
        if i < row:
            return self.check_up(i, mode_list[2])
        elif i > row:
            return self.check_down(i, mode_list[3])
        else:
            return i

    def col_processor(self, col, j, mode_list):
        if j < col:
            return self.check_left(j, mode_list[0])
        elif j > col:
            return self.check_right(j, mode_list[1])
        else:
            return j

    def count_neighbors(self, row, col, cell_type=AliveCell, mode_list=None):
        if mode_list is None:
            mode_list = self.mode_list
        count_cells = 0
        for i in range(row-1, row+2):
            row_val = self.row_processor(row, i, mode_list)
            for j in range(col-1, col+2):
                col_val = self.col_processor(col, j, mode_list)
                if row_val is not None and col_val is not None:
                    if isinstance(self.cells[row_val][col_val], cell_type):
                        count_cells += 1
        if isinstance(self.cells[row][col], cell_type):
            count_cells -= 1
        return count_cells

class GameRunner:
    def __init__(self, grid):
        self.grid = grid

    def update(self):
        temp_grid = self.grid.clone()
        for row in self.grid.cells:
            for cell in row:
                next_cell = cell.process()
                next_cell.grid = temp_grid
                temp_grid.set_cell(next_cell)
        self.grid = temp_grid

class ConwayGUI:
    def __init__(self):
        # Inicializar la ventana principal
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Juego de la Vida de Conway - Interfaz avanzada")
        self.root.geometry("1600x1000")  # Tamaño de ventana ampliado
        self.root.minsize(1200, 800)  # Establecer el tamaño mínimo de la ventana

        # Estado del juego
        self.grid_size = 30
        self.cell_size = 15
        self.max_canvas_size = 500  # Reducido para mejorar el rendimiento
        self.max_grid_size = 60  # Tamaño máximo de cuadrícula reducido para mejorar el rendimiento
        self.speed = 100  # ms entre iteraciones
        self.running = False
        self.grid = self.nuevo_grid()
        self.game_runner = GameRunner(self.grid)
        
        # Tipos de célula y colores
        self.cell_types = {
            "Dead": (DeadCell, "#000000"),
            "Alive": (AliveCell, "#00FF00"),
            "Cancer": (CancerCell, "#FF0000"),
            "Cure": (CureCell, "#0000FF")
        }
        self.selected_cell_type = "Alive"
        # Nombres visibles en español (las claves internas no cambian: se usan en los CSV)
        self.nombres_tipos = {"Dead": "Muerta", "Alive": "Viva", "Cancer": "Cáncer", "Cure": "Cura"}
        
        # Condiciones de contorno
        self.boundary_modes = ["normal", "normal", "normal", "normal"]  # izquierda, derecha, arriba, abajo
        
        # Seguimiento de estadísticas
        self.iteration_count = 0
        self.cell_history = []

        # Grabación de GIF
        self.recording_gif = False
        self.gif_frames = []
        self.max_gif_frames = 300  # Limitar los fotogramas para no agotar la memoria
        
        # Estado de la interfaz
        self.is_dragging = False
        self.drag_throttle = 0  # Para limitar los eventos de arrastre
        self.last_painted_cell = None  # Evitar pintar la misma célula varias veces
        
        self.setup_ui()
        self.update_canvas()
        self.update_charts()

        # Enlazar el evento de cambio de tamaño de la ventana
        self.root.bind("<Configure>", self.on_window_resize)
        
    def setup_ui(self):
        """Crea la disposición principal de la interfaz"""
        # Contenedor principal
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Panel izquierdo para el lienzo y los controles (con desplazamiento)
        left_panel = ctk.CTkScrollableFrame(main_frame, width=800, height=700)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 5))

        # Marco del lienzo con zona desplazable
        self.canvas_frame = ctk.CTkFrame(left_panel)
        self.canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Crear el marco desplazable para el lienzo
        self.canvas_scroll_frame = ctk.CTkScrollableFrame(
            self.canvas_frame,
            width=min(self.grid_size * self.cell_size + 40, self.max_canvas_size),
            height=min(self.grid_size * self.cell_size + 40, self.max_canvas_size)
        )
        self.canvas_scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Lienzo con espacio extra para los indicadores de contorno
        self.border_margin = 20  # Espacio para los indicadores de contorno
        canvas_width = self.grid_size * self.cell_size + (2 * self.border_margin)
        canvas_height = self.grid_size * self.cell_size + (2 * self.border_margin)

        self.canvas = tk.Canvas(
            self.canvas_scroll_frame,
            width=canvas_width,
            height=canvas_height,
            bg="black",
            highlightthickness=0
        )
        self.canvas.pack(padx=10, pady=10)
        
        # Enlazar los eventos del lienzo
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        
        # Marco de controles
        controls_frame = ctk.CTkFrame(left_panel)
        controls_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.setup_controls(controls_frame)
        self.setup_weight_controls(left_panel)
        self.setup_rules_controls(left_panel)
        self.setup_boundary_controls(left_panel)
        
        # Panel derecho para los gráficos
        right_panel = ctk.CTkFrame(main_frame)
        right_panel.pack(side="right", fill="both", padx=(5, 0))
        
        self.setup_charts(right_panel)
        
    def setup_controls(self, parent):
        """Crea los botones y deslizadores de control"""
        # Fila 1: controles de la simulación
        sim_frame = ctk.CTkFrame(parent)
        sim_frame.pack(fill="x", padx=5, pady=5)
        
        self.start_btn = ctk.CTkButton(sim_frame, text="Iniciar", command=self.start_simulation)
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = ctk.CTkButton(sim_frame, text="Parar", command=self.stop_simulation)
        self.stop_btn.pack(side="left", padx=5)
        
        self.step_btn = ctk.CTkButton(sim_frame, text="Paso", command=self.step_simulation)
        self.step_btn.pack(side="left", padx=5)
        
        self.clear_btn = ctk.CTkButton(sim_frame, text="Limpiar", command=self.clear_grid)
        self.clear_btn.pack(side="left", padx=5)
        
        # Fila 2: selección del tipo de célula
        cell_frame = ctk.CTkFrame(parent)
        cell_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(cell_frame, text="Tipo de célula:").pack(side="left", padx=5)
        
        self.cell_type_var = ctk.StringVar(value=self.nombres_tipos[self.selected_cell_type])
        self.cell_type_menu = ctk.CTkOptionMenu(
            cell_frame,
            variable=self.cell_type_var,
            values=list(self.nombres_tipos.values()),
            command=self.on_cell_type_change
        )
        self.cell_type_menu.pack(side="left", padx=5)

        # Opción: marcar en gris las casillas muertas que han tenido vida alguna vez (solo visual)
        self.mostrar_huella_var = ctk.BooleanVar(value=False)
        self.huella_switch = ctk.CTkSwitch(
            cell_frame, text="Marcar en gris las células que han tenido vida",
            variable=self.mostrar_huella_var, command=self.update_canvas
        )
        self.huella_switch.pack(side="left", padx=20)
        
        # Fila 3: deslizadores
        slider_frame = ctk.CTkFrame(parent)
        slider_frame.pack(fill="x", padx=5, pady=5)
        
        # Deslizador de velocidad
        speed_frame = ctk.CTkFrame(slider_frame)
        speed_frame.pack(side="left", fill="x", expand=True, padx=5)
        
        ctk.CTkLabel(speed_frame, text="Velocidad (ms):").pack()
        self.speed_slider = ctk.CTkSlider(
            speed_frame,
            from_=10,
            to=1000,
            number_of_steps=99,
            command=self.on_speed_change
        )
        self.speed_slider.set(self.speed)
        self.speed_slider.pack(fill="x", padx=5)
        
        self.speed_label = ctk.CTkLabel(speed_frame, text=f"{self.speed}ms")
        self.speed_label.pack()
        
        # Deslizador del tamaño de la cuadrícula
        size_frame = ctk.CTkFrame(slider_frame)
        size_frame.pack(side="left", fill="x", expand=True, padx=5)

        ctk.CTkLabel(size_frame, text="Tamaño de la cuadrícula:").pack()
        self.size_slider = ctk.CTkSlider(
            size_frame,
            from_=10,
            to=self.max_grid_size,
            number_of_steps=self.max_grid_size-10,
            command=self.on_size_change
        )
        self.size_slider.set(self.grid_size)
        self.size_slider.pack(fill="x", padx=5)

        self.size_label = ctk.CTkLabel(size_frame, text=f"{self.grid_size}x{self.grid_size}")
        self.size_label.pack()

        # Información del tamaño de celda
        self.cell_size_label = ctk.CTkLabel(size_frame, text=f"Tamaño de celda: {self.cell_size}px", font=("Arial", 10))
        self.cell_size_label.pack()
        
        # Fila 4: operaciones con archivos
        file_frame = ctk.CTkFrame(parent)
        file_frame.pack(fill="x", padx=5, pady=5)

        # Primera fila de operaciones con archivos
        file_row1 = ctk.CTkFrame(file_frame)
        file_row1.pack(fill="x", pady=2)

        self.save_btn = ctk.CTkButton(file_row1, text="Guardar cuadrícula", command=self.save_grid)
        self.save_btn.pack(side="left", padx=2, fill="x", expand=True)

        self.load_btn = ctk.CTkButton(file_row1, text="Cargar cuadrícula", command=self.load_grid)
        self.load_btn.pack(side="left", padx=2, fill="x", expand=True)

        # Segunda fila de operaciones con archivos
        file_row2 = ctk.CTkFrame(file_frame)
        file_row2.pack(fill="x", pady=2)

        self.save_graph_btn = ctk.CTkButton(file_row2, text="Guardar gráfico", command=self.save_line_graph)
        self.save_graph_btn.pack(side="left", padx=2, fill="x", expand=True)

        self.record_gif_btn = ctk.CTkButton(file_row2, text="Grabar GIF", command=self.toggle_gif_recording)
        self.record_gif_btn.pack(side="left", padx=2, fill="x", expand=True)

    def setup_weight_controls(self, parent):
        """Crea los controles de los pesos de las células"""
        weight_frame = ctk.CTkFrame(parent)
        weight_frame.pack(fill="x", padx=10, pady=(0, 10))

        # Cabecera
        header_frame = ctk.CTkFrame(weight_frame)
        header_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(header_frame, text="Pesos de las células:", font=("Arial", 14, "bold")).pack(side="left", padx=5)

        # Texto informativo
        info_text = "Rango: 0.0001 - 1.0 (con punto decimal) | Mayor valor = efecto más fuerte"
        ctk.CTkLabel(header_frame, text=info_text, font=("Arial", 10), text_color="gray").pack(side="right", padx=5)

        # Marco de controles
        controls_frame = ctk.CTkFrame(weight_frame)
        controls_frame.pack(fill="x", pady=5, padx=10)

        # Peso del cáncer
        cancer_frame = ctk.CTkFrame(controls_frame)
        cancer_frame.pack(side="left", fill="x", expand=True, padx=5)

        ctk.CTkLabel(cancer_frame, text="Peso del cáncer:", font=("Arial", 12, "bold")).pack(pady=2)
        self.cancer_weight_var = ctk.StringVar(value="0.01")
        self.cancer_weight_entry = ctk.CTkEntry(cancer_frame, textvariable=self.cancer_weight_var, width=100)
        self.cancer_weight_entry.pack(pady=2)
        self.cancer_weight_entry.bind("<KeyRelease>", self.on_cancer_weight_change)

        # Peso de la cura
        cure_frame = ctk.CTkFrame(controls_frame)
        cure_frame.pack(side="right", fill="x", expand=True, padx=5)

        ctk.CTkLabel(cure_frame, text="Peso de la cura:", font=("Arial", 12, "bold")).pack(pady=2)
        self.cure_weight_var = ctk.StringVar(value="0.1")
        self.cure_weight_entry = ctk.CTkEntry(cure_frame, textvariable=self.cure_weight_var, width=100)
        self.cure_weight_entry.pack(pady=2)
        self.cure_weight_entry.bind("<KeyRelease>", self.on_cure_weight_change)

    def setup_boundary_controls(self, parent):
        """Crea los controles de las condiciones de contorno"""
        boundary_frame = ctk.CTkFrame(parent)
        boundary_frame.pack(fill="x", padx=10, pady=(0, 10))

        # Cabecera con información
        header_frame = ctk.CTkFrame(boundary_frame)
        header_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(header_frame, text="Condiciones de contorno:", font=("Arial", 14, "bold")).pack(side="left", padx=5)

        # Etiqueta informativa
        info_text = "Normal: bordes muertos | Periódico: se conectan los extremos | Espejo: refleja"
        ctk.CTkLabel(header_frame, text=info_text, font=("Arial", 10), text_color="gray").pack(side="right", padx=5)

        # Crear los controles de contorno con una disposición más accesible
        grid_frame = ctk.CTkFrame(boundary_frame)
        grid_frame.pack(pady=5, fill="x")

        # Configurar los pesos de la rejilla para un espaciado correcto
        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)
        grid_frame.grid_columnconfigure(2, weight=1)
        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_rowconfigure(1, weight=1)
        grid_frame.grid_rowconfigure(2, weight=1)

        # Contorno superior
        top_frame = ctk.CTkFrame(grid_frame)
        top_frame.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        ctk.CTkLabel(top_frame, text="Arriba:", font=("Arial", 12, "bold")).pack(pady=2)
        self.top_boundary = ctk.CTkOptionMenu(
            top_frame,
            values=list(MODOS_TEXTO.values()),
            command=lambda x: self.set_boundary(2, x),
            width=120
        )
        self.top_boundary.set(MODOS_TEXTO["normal"])
        self.top_boundary.pack(pady=2)

        # Contorno izquierdo
        left_frame = ctk.CTkFrame(grid_frame)
        left_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        ctk.CTkLabel(left_frame, text="Izquierda:", font=("Arial", 12, "bold")).pack(pady=2)
        self.left_boundary = ctk.CTkOptionMenu(
            left_frame,
            values=list(MODOS_TEXTO.values()),
            command=lambda x: self.set_boundary(0, x),
            width=120
        )
        self.left_boundary.set(MODOS_TEXTO["normal"])
        self.left_boundary.pack(pady=2)

        # Espacio central (equilibrio visual)
        center_frame = ctk.CTkFrame(grid_frame)
        center_frame.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        ctk.CTkLabel(center_frame, text="Cuadrícula", font=("Arial", 12, "bold")).pack(pady=15)

        # Contorno derecho
        right_frame = ctk.CTkFrame(grid_frame)
        right_frame.grid(row=1, column=2, padx=10, pady=5, sticky="ew")
        ctk.CTkLabel(right_frame, text="Derecha:", font=("Arial", 12, "bold")).pack(pady=2)
        self.right_boundary = ctk.CTkOptionMenu(
            right_frame,
            values=list(MODOS_TEXTO.values()),
            command=lambda x: self.set_boundary(1, x),
            width=120
        )
        self.right_boundary.set(MODOS_TEXTO["normal"])
        self.right_boundary.pack(pady=2)

        # Contorno inferior
        bottom_frame = ctk.CTkFrame(grid_frame)
        bottom_frame.grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        ctk.CTkLabel(bottom_frame, text="Abajo:", font=("Arial", 12, "bold")).pack(pady=2)
        self.bottom_boundary = ctk.CTkOptionMenu(
            bottom_frame,
            values=list(MODOS_TEXTO.values()),
            command=lambda x: self.set_boundary(3, x),
            width=120
        )
        self.bottom_boundary.set(MODOS_TEXTO["normal"])
        self.bottom_boundary.pack(pady=2)

        # Añadir la leyenda de indicadores visuales
        legend_frame = ctk.CTkFrame(boundary_frame)
        legend_frame.pack(pady=10, fill="x")

        ctk.CTkLabel(legend_frame, text="Indicadores visuales:", font=("Arial", 12, "bold")).pack(pady=2)

        # Crear los elementos de la leyenda
        legend_items = [
            ("Normal (borde gris)", "#808080", "Bordes muertos - N"),
            ("Periódico (borde verde)", "#00FF00", "Los extremos se conectan - P"),
            ("Espejo (borde naranja)", "#FF8800", "Bordes reflectantes - E"),
            ("Casilla gris", "#9ca3af", "Muerta, pero ha tenido vida alguna vez")
        ]

        for text, color, description in legend_items:
            item_frame = ctk.CTkFrame(legend_frame)
            item_frame.pack(fill="x", padx=5, pady=1)

            # Indicador de color
            color_label = ctk.CTkLabel(item_frame, text="●", text_color=color, font=("Arial", 16))
            color_label.pack(side="left", padx=5)

            # Descripción
            desc_label = ctk.CTkLabel(item_frame, text=f"{text}: {description}", font=("Arial", 10))
            desc_label.pack(side="left", padx=5)

    def setup_charts(self, parent):
        """Crea los gráficos de matplotlib"""
        charts_frame = ctk.CTkFrame(parent)
        charts_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(charts_frame, text="Estadísticas", font=("Arial", 16, "bold")).pack(pady=5)

        # Crear la figura de matplotlib
        self.fig = Figure(figsize=(6, 8), facecolor='#2b2b2b')

        # Gráfico circular
        self.pie_ax = self.fig.add_subplot(2, 1, 1)
        self.pie_ax.set_facecolor('#2b2b2b')

        # Gráfico de líneas
        self.line_ax = self.fig.add_subplot(2, 1, 2)
        self.line_ax.set_facecolor('#2b2b2b')

        # Insertar en tkinter
        self.chart_canvas = FigureCanvasTkAgg(self.fig, charts_frame)
        self.chart_canvas.get_tk_widget().pack(fill="both", expand=True)

    def on_canvas_click(self, event):
        """Gestiona los clics sobre el lienzo"""
        if self.running:
            return

        self.is_dragging = True
        self.last_painted_cell = None
        self.drag_throttle = 0
        self.paint_cell(event.x, event.y)

    def on_canvas_drag(self, event):
        """Gestiona el arrastre sobre el lienzo (con limitación de eventos)"""
        if self.running or not self.is_dragging:
            return

        # Limitar los eventos de arrastre para reducir el retardo
        self.drag_throttle += 1
        if self.drag_throttle % 3 == 0:  # Procesar solo uno de cada 3 eventos de arrastre
            self.paint_cell(event.x, event.y)

    def on_canvas_release(self, event):
        """Gestiona cuando se suelta el botón sobre el lienzo"""
        was_dragging = self.is_dragging
        self.is_dragging = False
        self.last_painted_cell = None

        # Actualizar los gráficos al terminar de arrastrar
        if was_dragging:
            self.update_charts()

    def paint_cell(self, x, y):
        """Pinta una célula en las coordenadas del lienzo indicadas (optimizado)"""
        # Ajustar las coordenadas según el margen del borde
        adjusted_x = x - self.border_margin
        adjusted_y = y - self.border_margin
        col = adjusted_x // self.cell_size
        row = adjusted_y // self.cell_size

        if 0 <= row < self.grid_size and 0 <= col < self.grid_size:
            # Evitar pintar la misma célula varias veces al arrastrar
            current_cell = (row, col)
            if self.last_painted_cell == current_cell:
                return

            self.last_painted_cell = current_cell

            cell_class, _ = self.cell_types[self.selected_cell_type]
            new_cell = cell_class(row, col, self.grid)

            # Aplicar los pesos actuales a las células especiales
            if isinstance(new_cell, CancerCell):
                try:
                    new_cell.cancer_weighting = float(self.cancer_weight_var.get())
                except (ValueError, AttributeError):
                    new_cell.cancer_weighting = 0.01  # Por defecto
            elif isinstance(new_cell, CureCell):
                try:
                    new_cell.cure_weighting = float(self.cure_weight_var.get())
                except (ValueError, AttributeError):
                    new_cell.cure_weighting = 0.1  # Por defecto

            self.grid.cells[row][col] = new_cell
            if isinstance(new_cell, DeadCell):
                self.huella.discard((row, col))  # pintar "Muerta" actúa como borrador de la huella

            # Solo actualizar el lienzo; los gráficos se omiten al arrastrar para ir más rápido
            self.update_canvas()
            if not self.is_dragging:
                self.update_charts()

    def update_canvas(self):
        """Actualiza el lienzo (optimizado)"""
        self.canvas.delete("all")

        # Primero dibujar los indicadores de contorno (fondo)
        self.draw_boundary_indicators()

        # Fondo negro con líneas grises tenues: así las células muertas se ven siempre
        self.dibujar_cuadricula_base()

        # Después dibujar las células encima, desplazadas por el margen del borde
        for row in range(self.grid_size):
            for col in range(self.grid_size):
                x1 = col * self.cell_size + self.border_margin
                y1 = row * self.cell_size + self.border_margin
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size

                cell = self.grid.cells[row][col]
                cell_type = type(cell).__name__.replace("Cell", "")

                if cell_type in self.cell_types:
                    _, color = self.cell_types[cell_type]

                    # Solo visual: la casilla muerta que ha tenido vida alguna vez se pinta en gris
                    if cell_type != "Dead":
                        self.huella.add((row, col))
                    elif self.mostrar_huella_var.get() and (row, col) in self.huella:
                        self.canvas.create_rectangle(x1, y1, x2, y2, fill=self.color_grafico("Dead"),
                                                     outline="#555555" if self.grid_size <= 40 else "")

                    # Las muertas sin historia ya están representadas por el fondo negro y la rejilla
                    if cell_type != "Dead":
                        outline_color = "#555555" if self.grid_size <= 40 else ""
                        self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline=outline_color)

                        # Patrones visuales simplificados para mejorar el rendimiento
                        if self.cell_size >= 8:  # Añadir patrones solo si las celdas son lo bastante grandes
                            if cell_type == "Cancer":
                                # Patrón simple de aspa (X)
                                self.canvas.create_line(x1+1, y1+1, x2-1, y2-1, fill="white", width=1)
                                self.canvas.create_line(x1+1, y2-1, x2-1, y1+1, fill="white", width=1)
                            elif cell_type == "Cure":
                                # Patrón simple de cruz (+)
                                mid_x = (x1 + x2) // 2
                                mid_y = (y1 + y2) // 2
                                self.canvas.create_line(mid_x, y1+2, mid_x, y2-2, fill="white", width=1)
                                self.canvas.create_line(x1+2, mid_y, x2-2, mid_y, fill="white", width=1)
                            elif cell_type == "Alive":
                                # Patrón simple de punto
                                mid_x = (x1 + x2) // 2
                                mid_y = (y1 + y2) // 2
                                self.canvas.create_oval(mid_x-1, mid_y-1, mid_x+1, mid_y+1, fill="white", outline="white")

    def draw_boundary_indicators(self):
        """Dibuja indicadores visuales alrededor del lienzo para mostrar las condiciones de contorno"""
        grid_width = self.grid_size * self.cell_size
        grid_height = self.grid_size * self.cell_size

        # Definir los colores de cada modo de contorno
        boundary_colors = {
            "normal": "#808080",    # Gris
            "periodic": "#00FF00",  # Verde
            "mirror": "#FF8800"     # Naranja
        }

        # Dibujar franjas de color en las zonas del margen

        # Contorno izquierdo (índice 0)
        left_color = boundary_colors[self.boundary_modes[0]]
        self.canvas.create_rectangle(2, self.border_margin, self.border_margin - 2,
                                   self.border_margin + grid_height,
                                   fill=left_color, outline=left_color, tags="boundary")

        # Contorno derecho (índice 1)
        right_color = boundary_colors[self.boundary_modes[1]]
        self.canvas.create_rectangle(self.border_margin + grid_width + 2, self.border_margin,
                                   self.border_margin + grid_width + self.border_margin - 2,
                                   self.border_margin + grid_height,
                                   fill=right_color, outline=right_color, tags="boundary")

        # Contorno superior (índice 2)
        top_color = boundary_colors[self.boundary_modes[2]]
        self.canvas.create_rectangle(self.border_margin, 2,
                                   self.border_margin + grid_width, self.border_margin - 2,
                                   fill=top_color, outline=top_color, tags="boundary")

        # Contorno inferior (índice 3)
        bottom_color = boundary_colors[self.boundary_modes[3]]
        self.canvas.create_rectangle(self.border_margin, self.border_margin + grid_height + 2,
                                   self.border_margin + grid_width,
                                   self.border_margin + grid_height + self.border_margin - 2,
                                   fill=bottom_color, outline=bottom_color, tags="boundary")

        # Añadir etiquetas de texto
        self.draw_boundary_labels(grid_width, grid_height)

    def draw_boundary_labels(self, grid_width, grid_height):
        """Dibuja etiquetas de texto con los modos de contorno en las zonas del borde"""
        # Mostrar etiquetas solo si hay espacio suficiente
        if self.border_margin >= 15:
            # Abreviaturas de los modos para mostrarlos de forma compacta
            mode_text = {
                "normal": "N",
                "periodic": "P",
                "mirror": "E"
            }

            # Color del texto para que se vea bien
            text_color = "white"
            font_size = max(8, min(12, self.border_margin // 2))

            # Etiqueta del contorno izquierdo
            self.canvas.create_text(self.border_margin // 2,
                                  self.border_margin + grid_height // 2,
                                  text=mode_text[self.boundary_modes[0]],
                                  fill=text_color, font=("Arial", font_size, "bold"),
                                  tags="boundary")

            # Etiqueta del contorno derecho
            self.canvas.create_text(self.border_margin + grid_width + self.border_margin // 2,
                                  self.border_margin + grid_height // 2,
                                  text=mode_text[self.boundary_modes[1]],
                                  fill=text_color, font=("Arial", font_size, "bold"),
                                  tags="boundary")

            # Etiqueta del contorno superior
            self.canvas.create_text(self.border_margin + grid_width // 2,
                                  self.border_margin // 2,
                                  text=mode_text[self.boundary_modes[2]],
                                  fill=text_color, font=("Arial", font_size, "bold"),
                                  tags="boundary")

            # Etiqueta del contorno inferior
            self.canvas.create_text(self.border_margin + grid_width // 2,
                                  self.border_margin + grid_height + self.border_margin // 2,
                                  text=mode_text[self.boundary_modes[3]],
                                  fill=text_color, font=("Arial", font_size, "bold"),
                                  tags="boundary")

    def update_charts(self):
        """Actualiza el gráfico circular y el de líneas"""
        # Contar los tipos de célula
        counts = {"Dead": 0, "Alive": 0, "Cancer": 0, "Cure": 0}

        for row in range(self.grid_size):
            for col in range(self.grid_size):
                cell = self.grid.cells[row][col]
                cell_type = type(cell).__name__.replace("Cell", "")
                if cell_type in counts:
                    counts[cell_type] += 1

        # Guardar el historial para el gráfico de líneas
        self.cell_history.append(counts.copy())

        # Borrar los gráficos anteriores
        self.pie_ax.clear()
        self.line_ax.clear()

        # Gráfico circular
        non_zero_counts = {k: v for k, v in counts.items() if v > 0}
        if non_zero_counts:
            colors = [self.color_grafico(cell_type) for cell_type in non_zero_counts.keys()]
            nombres = [self.nombres_tipos[cell_type] for cell_type in non_zero_counts.keys()]
            self.pie_ax.pie(non_zero_counts.values(), labels=nombres,
                           colors=colors, autopct='%1.1f%%', textprops={'color': 'white'},
                           wedgeprops={'edgecolor': '#d1d5db', 'linewidth': 0.8})
            self.pie_ax.set_title(f"Distribución de células (iteración {self.iteration_count})", color='white')

        # Gráfico de líneas
        if len(self.cell_history) > 1:
            iterations = range(len(self.cell_history))
            for cell_type in counts.keys():
                values = [h[cell_type] for h in self.cell_history]
                color = self.color_grafico(cell_type, linea=True)
                self.line_ax.plot(iterations, values, label=self.nombres_tipos[cell_type], color=color, linewidth=2)

            self.line_ax.set_xlabel("Iteración", color='white')
            self.line_ax.set_ylabel("Nº de células", color='white')
            self.line_ax.set_title("Población de células a lo largo del tiempo", color='white')
            self.line_ax.legend()
            self.line_ax.tick_params(colors='white')
            self.line_ax.grid(True, alpha=0.3)

        # Refrescar el lienzo
        self.chart_canvas.draw()

    def start_simulation(self):
        """Inicia la simulación"""
        if not self.running:
            self.running = True
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.simulation_thread = threading.Thread(target=self.run_simulation, daemon=True)
            self.simulation_thread.start()

    def stop_simulation(self):
        """Detiene la simulación"""
        self.running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def save_line_graph(self):
        """Guarda el gráfico de líneas como imagen PNG"""
        # Comprobar si hay datos que merezca la pena guardar
        if len(self.cell_history) < 2:
            messagebox.showwarning(
                "Sin datos",
                "No hay datos para el gráfico de líneas. Ejecuta antes una simulación para generarlos."
            )
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("Archivos PNG", "*.png"), ("Todos los archivos", "*.*")],
            title="Guardar gráfico de líneas"
        )

        if filename:
            try:
                # Crear una figura nueva para guardar (independiente de la interfaz)
                save_fig, save_ax = plt.subplots(figsize=(10, 6))
                save_ax.set_title("Población de células a lo largo del tiempo", fontsize=14, fontweight='bold')
                save_ax.set_xlabel("Iteración", fontsize=12)
                save_ax.set_ylabel("Nº de células", fontsize=12)
                save_ax.grid(True, alpha=0.3)

                # Dibujar los datos
                iterations = list(range(len(self.cell_history)))
                for cell_type in ["Dead", "Alive", "Cancer", "Cure"]:
                    counts = [data[cell_type] for data in self.cell_history]
                    color = self.cell_types[cell_type][1]  # Obtener el color de cell_types
                    save_ax.plot(iterations, counts, label=self.nombres_tipos[cell_type], color=color, linewidth=2)

                save_ax.legend(fontsize=10)
                save_ax.set_xlim(0, max(1, len(self.cell_history) - 1))

                # Añadir el texto de metadatos
                metadata_text = (
                    f"Tamaño de la cuadrícula: {self.grid_size}x{self.grid_size}\n"
                    f"Iteraciones totales: {len(self.cell_history)}\n"
                    f"Regla de reproducción: {REGLAS.notacion()}\n"
                    f"Contornos: Izq:{self.boundary_modes[0]}, Der:{self.boundary_modes[1]}, "
                    f"Arr:{self.boundary_modes[2]}, Aba:{self.boundary_modes[3]}"
                )
                save_ax.text(0.02, 0.98, metadata_text, transform=save_ax.transAxes,
                           fontsize=9, verticalalignment='top',
                           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

                # Guardar la figura
                save_fig.tight_layout()
                save_fig.savefig(filename, dpi=300, bbox_inches='tight')
                plt.close(save_fig)  # Liberar recursos

                messagebox.showinfo("Éxito", f"Gráfico de líneas guardado en {filename}")

            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar el gráfico de líneas: {str(e)}")

    def toggle_gif_recording(self):
        """Activa o desactiva la grabación del GIF"""
        if not self.recording_gif:
            self.start_gif_recording()
        else:
            self.stop_gif_recording()

    def start_gif_recording(self):
        """Empieza a grabar fotogramas para el GIF"""
        self.recording_gif = True
        self.gif_frames = []
        self.record_gif_btn.configure(text="Detener grabación", fg_color="#dc2626")  # Color rojo

        # Capturar el primer fotograma
        self.capture_gif_frame()

        messagebox.showinfo("Grabación iniciada",
                          f"¡Grabación de GIF iniciada!\n"
                          f"Máximo de fotogramas: {self.max_gif_frames}\n"
                          f"Ejecuta tu simulación y pulsa 'Detener grabación' al terminar.")

    def stop_gif_recording(self):
        """Detiene la grabación y ofrece guardar el GIF"""
        self.recording_gif = False
        self.record_gif_btn.configure(text="Grabar GIF", fg_color=["#3B8ED0", "#1F6AA5"])  # Azul por defecto de CTk

        if len(self.gif_frames) < 2:
            messagebox.showwarning("Sin fotogramas",
                                 "No se han grabado suficientes fotogramas. Se necesitan al menos 2 para un GIF.")
            return

        # Ofrecer guardar el GIF
        result = messagebox.askyesno("Guardar GIF",
                                   f"Se han grabado {len(self.gif_frames)} fotogramas.\n"
                                   "¿Quieres guardarlo como GIF animado?")
        if result:
            self.save_gif()

        # Borrar los fotogramas después de procesarlos
        self.gif_frames = []

        # Forzar la actualización del estado del botón
        self.root.update_idletasks()

    def capture_gif_frame(self):
        """Captura el estado actual del lienzo como fotograma del GIF"""
        if not self.recording_gif or len(self.gif_frames) >= self.max_gif_frames:
            return

        try:
            # Obtener las dimensiones del lienzo
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            # Crear una imagen PIL a partir del lienzo
            # Se crea una versión simplificada dibujando el estado de la cuadrícula
            frame = Image.new('RGB', (canvas_width, canvas_height), 'black')
            draw = ImageDraw.Draw(frame)

            # Rejilla tenue para distinguir las células muertas
            lado = self.grid_size * self.cell_size
            draw.rectangle([self.border_margin, self.border_margin,
                            self.border_margin + lado - 1, self.border_margin + lado - 1], outline="#555555")
            if self.cell_size >= 4:
                for k in range(1, self.grid_size):
                    p = self.border_margin + k * self.cell_size
                    draw.line([(p, self.border_margin), (p, self.border_margin + lado - 1)], fill="#2e2e2e")
                    draw.line([(self.border_margin, p), (self.border_margin + lado - 1, p)], fill="#2e2e2e")

            # Dibujar el estado de la cuadrícula
            for row in range(self.grid_size):
                for col in range(self.grid_size):
                    cell = self.grid.cells[row][col]
                    cell_type = type(cell).__name__.replace("Cell", "")

                    if cell_type in self.cell_types:
                        color = self.cell_types[cell_type][1]

                        # Calcular la posición de la célula con el margen del borde
                        x1 = col * self.cell_size + self.border_margin
                        y1 = row * self.cell_size + self.border_margin
                        x2 = x1 + self.cell_size - 1
                        y2 = y1 + self.cell_size - 1

                        # Dibujar solo las células no muertas para un GIF más limpio
                        if cell_type != "Dead":
                            draw.rectangle([x1, y1, x2, y2], fill=color)
                        elif self.mostrar_huella_var.get() and (row, col) in self.huella:
                            draw.rectangle([x1, y1, x2, y2], fill=self.color_grafico("Dead"))

            # Añadir el número de fotograma
            frame_text = f"Fotograma {len(self.gif_frames) + 1}"
            draw.text((10, 10), frame_text, fill="white")

            self.gif_frames.append(frame)

        except Exception as e:
            print(f"Error al capturar el fotograma del GIF: {e}")

    def save_gif(self):
        """Guarda los fotogramas grabados como GIF animado"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".gif",
            filetypes=[("Archivos GIF", "*.gif"), ("Todos los archivos", "*.*")],
            title="Guardar GIF animado"
        )

        if filename:
            try:
                # Guardar como GIF animado
                duration = max(100, self.speed)  # Usar la velocidad de la simulación, mínimo 100 ms

                self.gif_frames[0].save(
                    filename,
                    save_all=True,
                    append_images=self.gif_frames[1:],
                    duration=duration,
                    loop=0  # Repetir indefinidamente
                )

                messagebox.showinfo("Éxito",
                                  f"GIF animado guardado en {filename}\n"
                                  f"Fotogramas: {len(self.gif_frames)}\n"
                                  f"Duración: {duration} ms por fotograma")

                # Borrar los fotogramas para liberar memoria
                self.gif_frames = []

            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar el GIF: {str(e)}")

    def step_simulation(self):
        """Realiza un paso de la simulación"""
        if not self.running:
            self.marcar_vida()  # anota el estado actual antes de avanzar
            self.game_runner.update()
            self.grid = self.game_runner.grid
            self.marcar_vida()
            self.iteration_count += 1
            self.update_canvas()
            self.update_charts()

            # Capturar fotograma para el GIF si se está grabando
            if self.recording_gif:
                self.capture_gif_frame()

    def run_simulation(self):
        """Bucle principal de la simulación"""
        while self.running:
            self.marcar_vida()  # anota el estado actual antes de avanzar
            self.game_runner.update()
            self.grid = self.game_runner.grid
            self.marcar_vida()
            self.iteration_count += 1

            # Actualizar la interfaz en el hilo principal
            self.root.after(0, self.update_canvas)
            self.root.after(0, self.update_charts)

            # Capturar fotograma para el GIF si se está grabando
            if self.recording_gif:
                self.root.after(0, self.capture_gif_frame)

            time.sleep(self.speed / 1000.0)

    def clear_grid(self):
        """Vaciar la cuadrícula"""
        if not self.running:
            self.grid = self.nuevo_grid()
            self.game_runner = GameRunner(self.grid)
            self.iteration_count = 0
            self.cell_history = []

            # Reiniciar la grabación del GIF
            if self.recording_gif:
                self.stop_gif_recording()

            self.update_canvas()
            self.update_charts()

    def on_cell_type_change(self, value):
        """Gestiona el cambio del tipo de célula seleccionado"""
        self.selected_cell_type = self.nombre_a_tipo(value)

    def on_cancer_weight_change(self, event=None):
        """Gestiona el cambio del peso del cáncer"""
        try:
            weight = float(self.cancer_weight_var.get())
            # Limitar al rango válido
            weight = max(0.0001, min(1.0, weight))

            # Actualizar todas las células de cáncer existentes
            for row in range(self.grid_size):
                for col in range(self.grid_size):
                    cell = self.grid.cells[row][col]
                    if isinstance(cell, CancerCell):
                        cell.cancer_weighting = weight

            # Actualizar el valor mostrado si se limitó
            if weight != float(self.cancer_weight_var.get()):
                self.cancer_weight_var.set(str(weight))

        except ValueError:
            # Entrada no válida: se ignora
            pass

    def on_cure_weight_change(self, event=None):
        """Gestiona el cambio del peso de la cura"""
        try:
            weight = float(self.cure_weight_var.get())
            # Limitar al rango válido
            weight = max(0.0001, min(1.0, weight))

            # Actualizar todas las células de cura existentes
            for row in range(self.grid_size):
                for col in range(self.grid_size):
                    cell = self.grid.cells[row][col]
                    if isinstance(cell, CureCell):
                        cell.cure_weighting = weight

            # Actualizar el valor mostrado si se limitó
            if weight != float(self.cure_weight_var.get()):
                self.cure_weight_var.set(str(weight))

        except ValueError:
            # Entrada no válida: se ignora
            pass

    def on_speed_change(self, value):
        """Gestiona el cambio del deslizador de velocidad"""
        self.speed = int(value)
        self.speed_label.configure(text=f"{self.speed}ms")

    def on_size_change(self, value):
        """Gestiona el cambio de tamaño de la cuadrícula con escalado adaptable"""
        if not self.running:
            new_size = int(value)
            if new_size != self.grid_size:
                self.grid_size = new_size
                self.size_label.configure(text=f"{self.grid_size}x{self.grid_size}")

                # Calcular un tamaño de celda adaptable para que el lienzo sea manejable
                max_canvas_dimension = self.max_canvas_size
                if self.grid_size * self.cell_size > max_canvas_dimension:
                    self.cell_size = max(1, max_canvas_dimension // self.grid_size)
                else:
                    # Tamaño de celda por defecto para cuadrículas pequeñas
                    self.cell_size = min(15, max(3, max_canvas_dimension // self.grid_size))

                # Actualizar la etiqueta del tamaño de celda
                self.cell_size_label.configure(text=f"Tamaño de celda: {self.cell_size}px")

                # Calcular el nuevo tamaño del lienzo incluyendo el margen del borde
                grid_size = self.grid_size * self.cell_size
                new_canvas_width = grid_size + (2 * self.border_margin)
                new_canvas_height = grid_size + (2 * self.border_margin)

                # Actualizar el tamaño del lienzo
                self.canvas.configure(width=new_canvas_width, height=new_canvas_height)

                # Actualizar el tamaño del marco desplazable
                scroll_width = min(new_canvas_width + 40, self.max_canvas_size)
                scroll_height = min(new_canvas_height + 40, self.max_canvas_size)
                self.canvas_scroll_frame.configure(width=scroll_width, height=scroll_height)

                # Crear una cuadrícula nueva
                self.grid = self.nuevo_grid()
                self.game_runner = GameRunner(self.grid)
                self.iteration_count = 0
                self.cell_history = []
                self.update_canvas()
                self.update_charts()

    def set_boundary(self, index, mode):
        """Establece la condición de contorno de un borde concreto"""
        mode = self.texto_a_modo(mode)
        self.boundary_modes[index] = mode
        # Actualizar los modos de contorno de la cuadrícula
        if hasattr(self.grid, 'mode_list'):
            self.grid.mode_list = self.boundary_modes.copy()

        # Refrescar los indicadores visuales
        self.update_canvas()

    def save_grid(self):
        """Guarda el estado de la cuadrícula y la configuración en un CSV"""
        if not self.running:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")]
            )

            if filename:
                try:
                    with open(filename, 'w', newline='') as csvfile:
                        writer = csv.writer(csvfile)

                        # Escribir la configuración
                        writer.writerow(["Settings"])
                        writer.writerow(["grid_size", self.grid_size])
                        writer.writerow(["speed", self.speed])
                        writer.writerow(["boundary_modes"] + self.boundary_modes)
                        writer.writerow(["cancer_weight", self.cancer_weight_var.get()])
                        writer.writerow(["cure_weight", self.cure_weight_var.get()])
                        for fila_regla in REGLAS.a_filas():
                            writer.writerow(fila_regla)
                        writer.writerow([])  # Fila vacía como separador

                        # Escribir los datos de la cuadrícula
                        writer.writerow(["Grid"])
                        for row in range(self.grid_size):
                            grid_row = []
                            for col in range(self.grid_size):
                                cell = self.grid.cells[row][col]
                                cell_type = type(cell).__name__.replace("Cell", "")
                                grid_row.append(cell_type)
                            writer.writerow(grid_row)

                    messagebox.showinfo("Éxito", f"Cuadrícula guardada en {filename}")
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo guardar la cuadrícula: {str(e)}")

    def load_grid(self):
        """Carga el estado de la cuadrícula y la configuración desde un CSV"""
        if not self.running:
            filename = filedialog.askopenfilename(
                filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")]
            )

            if filename:
                try:
                    with open(filename, 'r') as csvfile:
                        reader = csv.reader(csvfile)
                        rows = list(reader)

                    # Leer la configuración
                    settings_start = 0
                    for i, row in enumerate(rows):
                        if row and row[0] == "Settings":
                            settings_start = i + 1
                            break

                    # Cargar la configuración
                    for i in range(settings_start, len(rows)):
                        row = rows[i]
                        if not row:  # Fila vacía: fin de la configuración
                            break

                        if REGLAS.cargar_fila(row):
                            continue
                        if row[0] == "grid_size":
                            self.grid_size = int(row[1])
                            self.size_slider.set(self.grid_size)
                            self.size_label.configure(text=f"{self.grid_size}x{self.grid_size}")

                            # Actualizar el tamaño de celda según la cuadrícula cargada
                            max_canvas_dimension = self.max_canvas_size
                            if self.grid_size * self.cell_size > max_canvas_dimension:
                                self.cell_size = max(1, max_canvas_dimension // self.grid_size)
                            else:
                                # Tamaño de celda por defecto para cuadrículas pequeñas
                                self.cell_size = min(15, max(3, max_canvas_dimension // self.grid_size))

                            # Actualizar la etiqueta del tamaño de celda
                            self.cell_size_label.configure(text=f"Tamaño de celda: {self.cell_size}px")
                        elif row[0] == "speed":
                            self.speed = int(row[1])
                            self.speed_slider.set(self.speed)
                            self.speed_label.configure(text=f"{self.speed}ms")
                        elif row[0] == "boundary_modes":
                            self.boundary_modes = row[1:5]
                            # Actualizar los menús de contorno
                            self.left_boundary.set(self.modo_a_texto(self.boundary_modes[0]))
                            self.right_boundary.set(self.modo_a_texto(self.boundary_modes[1]))
                            self.top_boundary.set(self.modo_a_texto(self.boundary_modes[2]))
                            self.bottom_boundary.set(self.modo_a_texto(self.boundary_modes[3]))
                        elif row[0] == "cancer_weight":
                            try:
                                weight = float(row[1])
                                weight = max(0.0001, min(1.0, weight))  # Limitar al rango válido
                                self.cancer_weight_var.set(str(weight))
                            except (ValueError, IndexError):
                                self.cancer_weight_var.set("0.01")  # Por defecto
                        elif row[0] == "cure_weight":
                            try:
                                weight = float(row[1])
                                weight = max(0.0001, min(1.0, weight))  # Limitar al rango válido
                                self.cure_weight_var.set(str(weight))
                            except (ValueError, IndexError):
                                self.cure_weight_var.set("0.1")  # Por defecto

                    # Buscar los datos de la cuadrícula
                    grid_start = 0
                    for i, row in enumerate(rows):
                        if row and row[0] == "Grid":
                            grid_start = i + 1
                            break

                    # Crear una cuadrícula nueva
                    self.grid = self.nuevo_grid()

                    # Cargar los datos de la cuadrícula
                    for row_idx in range(self.grid_size):
                        if grid_start + row_idx < len(rows):
                            row_data = rows[grid_start + row_idx]
                            for col_idx in range(min(len(row_data), self.grid_size)):
                                cell_type = row_data[col_idx]
                                if cell_type in self.cell_types:
                                    cell_class, _ = self.cell_types[cell_type]
                                    new_cell = cell_class(row_idx, col_idx, self.grid)

                                    # Aplicar los pesos cargados a las células especiales
                                    if isinstance(new_cell, CancerCell):
                                        try:
                                            new_cell.cancer_weighting = float(self.cancer_weight_var.get())
                                        except (ValueError, AttributeError):
                                            new_cell.cancer_weighting = 0.01
                                    elif isinstance(new_cell, CureCell):
                                        try:
                                            new_cell.cure_weighting = float(self.cure_weight_var.get())
                                        except (ValueError, AttributeError):
                                            new_cell.cure_weighting = 0.1

                                    self.grid.cells[row_idx][col_idx] = new_cell

                    # Actualizar el simulador y la interfaz
                    self.game_runner = GameRunner(self.grid)
                    if hasattr(self.grid, 'mode_list'):
                        self.grid.mode_list = self.boundary_modes.copy()

                    # Redimensionar el lienzo incluyendo el margen del borde
                    grid_size = self.grid_size * self.cell_size
                    new_canvas_width = grid_size + (2 * self.border_margin)
                    new_canvas_height = grid_size + (2 * self.border_margin)
                    self.canvas.configure(width=new_canvas_width, height=new_canvas_height)

                    # Actualizar el tamaño del marco desplazable
                    scroll_width = min(new_canvas_width + 40, self.max_canvas_size)
                    scroll_height = min(new_canvas_height + 40, self.max_canvas_size)
                    self.canvas_scroll_frame.configure(width=scroll_width, height=scroll_height)

                    # Reiniciar las estadísticas
                    self.iteration_count = 0
                    self.cell_history = []

                    # Reiniciar la grabación del GIF
                    if self.recording_gif:
                        self.stop_gif_recording()

                    self.update_canvas()
                    self.update_charts()

                    self.refrescar_controles_reglas()
                    messagebox.showinfo("Éxito", f"Cuadrícula cargada desde {filename}")
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo cargar la cuadrícula: {str(e)}")

    # ------------------------------------------------------------------
    # Ayudas: traducción de nombres, colores y creación de cuadrículas
    # ------------------------------------------------------------------
    def modo_a_texto(self, modo):
        """Nombre visible (español) de un modo de contorno interno."""
        return MODOS_TEXTO.get(modo, modo)

    def texto_a_modo(self, texto):
        """Modo de contorno interno a partir del nombre visible (o del propio modo)."""
        for modo, nombre in MODOS_TEXTO.items():
            if texto == nombre:
                return modo
        return texto

    def nombre_a_tipo(self, nombre):
        """Clave interna del tipo de célula a partir de su nombre en español."""
        for tipo, visible in self.nombres_tipos.items():
            if nombre == visible:
                return tipo
        return nombre

    def color_grafico(self, tipo, linea=False):
        """Color de un tipo de célula en los gráficos.

        Las células muertas son negras, igual que el fondo de los gráficos, y no se
        verían: en los gráficos se representan en gris (con borde en el circular).
        """
        if tipo == "Dead":
            return "#9ca3af" if linea else "#4b5563"
        return self.cell_types[tipo][1]

    def nuevo_grid(self):
        """Crea una cuadrícula vacía respetando los contornos elegidos por el usuario."""
        modos = list(getattr(self, "boundary_modes", ["normal"] * 4))
        # Casillas que han tenido vida alguna vez (solo visual). Se reinicia con cada cuadrícula nueva.
        self.huella = set()
        return Grid(self.grid_size, self.grid_size, modos)

    def marcar_vida(self):
        """Anota las casillas ocupadas por alguna célula (viva, de cáncer o de cura).

        Es solo visual: las casillas muertas que ya tuvieron vida se pintan en gris.
        """
        for i, fila in enumerate(self.grid.cells):
            for j, celda in enumerate(fila):
                if not isinstance(celda, DeadCell):
                    self.huella.add((i, j))

    def dibujar_cuadricula_base(self):
        """Dibuja el fondo negro de la cuadrícula con líneas grises tenues.

        Así las células muertas se distinguen siempre (también en cuadrículas grandes)
        sin dibujar un rectángulo por cada una.
        """
        lado = self.grid_size * self.cell_size
        m = self.border_margin
        self.canvas.create_rectangle(m, m, m + lado, m + lado, fill="#000000", outline="#555555")
        if self.cell_size >= 4:
            for k in range(1, self.grid_size):
                p = m + k * self.cell_size
                self.canvas.create_line(p, m, p, m + lado, fill="#2e2e2e")
                self.canvas.create_line(m, p, m + lado, p, fill="#2e2e2e")

    # ------------------------------------------------------------------
    # Panel gráfico de reglas
    # ------------------------------------------------------------------
    def setup_rules_controls(self, parent):
        """Panel para configurar gráficamente nacimiento, supervivencia, cura y muerte"""
        self.param_widgets = {}      # clave -> (deslizador, etiqueta de valor, entero, decimales)
        self.botones_vecinas = {}    # clave -> lista de 9 botones (0..8 vecinas)
        self.vistas_vecinas = {}     # clave -> (lienzo, etiqueta de ejemplo)
        self.vecinas_ejemplo = {}    # clave -> nº de vecinas mostrado en la vista previa
        self.textos_reglas = {}      # clave -> etiqueta con la explicación matemática

        marco = ctk.CTkFrame(parent)
        marco.pack(fill="x", padx=10, pady=(0, 10))

        cabecera = ctk.CTkFrame(marco)
        cabecera.pack(fill="x", pady=5)
        ctk.CTkLabel(cabecera, text="Reglas del juego:", font=("Arial", 14, "bold")).pack(side="left", padx=5)
        self.regla_notacion_label = ctk.CTkLabel(
            cabecera, text="", font=("Courier New", 14, "bold"), text_color="#4ade80")
        self.regla_notacion_label.pack(side="left", padx=10)
        ctk.CTkButton(
            cabecera, text="Restaurar todo a valores por defecto",
            fg_color="#b45309", hover_color="#92400e",
            command=lambda: self.restaurar_reglas(None)
        ).pack(side="right", padx=5)

        ctk.CTkLabel(
            marco,
            text=("Los cambios se aplican en la siguiente generación, incluso con la simulación en marcha. "
                  "Notación N/S: N = nº de vecinas vivas con el que nace una célula (nacimiento), "
                  "S = nº con el que sobrevive (supervivencia)."),
            font=("Arial", 10), text_color="gray", wraplength=720, justify="left"
        ).pack(anchor="w", padx=10)

        pestanas = ctk.CTkTabview(marco, height=640)
        pestanas.pack(fill="x", padx=5, pady=5)

        # --- Pestaña: Nacimiento -------------------------------------------
        t = pestanas.add("Nacimiento")
        self._crear_selector_vecinas(
            t, "nacimiento", "Una célula MUERTA nace si tiene este nº de vecinas vivas "
                             "(pulsa los números para activarlos o desactivarlos):")
        self._crear_titulo(t, "Nacimiento de cáncer (célula muerta junto a cáncer)")
        self._crear_parametro(t, "cancer_nace_min", "Vecinas de cáncer mínimas", 1, 8, 7)
        self._crear_parametro(t, "cancer_nace_prob", "Probabilidad base de que nazca cáncer", 0, 1, 100, False, 2)
        self._crear_parametro(t, "cancer_nace_peso_ref", "Peso de referencia del cáncer", 0.001, 1, 999, False, 3)
        self._crear_texto(t, "cancer_nace")
        self._crear_titulo(t, "Nacimiento de cura (célula muerta rodeada de cáncer)")
        self._crear_parametro(t, "cura_nace_min", "Vecinas de cáncer mínimas", 1, 8, 7)
        self._crear_parametro(t, "cura_nace_prob", "Probabilidad base de que nazca cura", 0, 1, 100, False, 2)
        self._crear_parametro(t, "cura_nace_peso_ref", "Peso de referencia de la cura", 0.001, 1, 999, False, 3)
        self._crear_texto(t, "cura_nace")
        self._crear_boton_defecto(t, "nacimiento")

        # --- Pestaña: Supervivencia ----------------------------------------
        t = pestanas.add("Supervivencia")
        self._crear_selector_vecinas(
            t, "supervivencia", "Una célula VIVA sobrevive si tiene este nº de vecinas vivas "
                                "(pulsa los números para activarlos o desactivarlos):")
        self._crear_titulo(t, "Muerte de las células vivas por cáncer")
        self._crear_parametro(t, "viva_muere_cancer_min",
                              "Muere si tiene ≥ N vecinas de cáncer (0 = desactivado)", 0, 8, 8)
        self._crear_texto(t, "viva_muere_cancer")
        self._crear_boton_defecto(t, "supervivencia")

        # --- Pestaña: Cáncer (curación y muerte) ---------------------------
        t = pestanas.add("Cáncer")
        self._crear_titulo(t, "Curación del cáncer (pasa a célula viva)")
        self._crear_parametro(t, "cancer_curado_min", "Vecinas de cura mínimas", 1, 8, 7)
        self._crear_parametro(t, "cancer_curado_prob", "Probabilidad base de curación", 0, 1, 100, False, 2)
        self._crear_parametro(t, "cancer_curado_peso_ref", "Peso de referencia de la cura", 0.001, 1, 999, False, 3)
        self._crear_parametro(t, "cancer_resistencia", "Resistencia del cáncer a la cura", 0, 1, 100, False, 2)
        self._crear_parametro(t, "cancer_resistencia_peso_ref", "Peso de referencia del cáncer", 0.001, 1, 999, False, 3)
        self._crear_parametro(t, "cancer_curado_prob_min", "Probabilidad mínima de curación", 0, 1, 100, False, 2)
        self._crear_texto(t, "cancer_curado")
        self._crear_titulo(t, "Muerte del cáncer por sobrepoblación")
        self._crear_parametro(t, "cancer_satura_base", "Umbral base de vecinas de cáncer", 0, 8, 8)
        self._crear_parametro(t, "cancer_satura_min", "Umbral mínimo", 0, 8, 8)
        self._crear_parametro(t, "cancer_satura_peso_ref", "Peso de referencia del cáncer", 0.001, 1, 999, False, 3)
        self._crear_texto(t, "cancer_satura")
        self._crear_boton_defecto(t, "cancer")

        # --- Pestaña: Cura (muerte) ----------------------------------------
        t = pestanas.add("Cura")
        self._crear_titulo(t, "Peso de la cura cuando no hay ninguna cura cerca")
        self._crear_parametro(t, "cura_peso_defecto", "Peso por defecto", 0.001, 1, 999, False, 3)
        self._crear_titulo(t, "Muerte de la cura por aislamiento (demasiadas vecinas muertas)")
        self._crear_parametro(t, "cura_aislada_base", "Umbral base de vecinas muertas", 0, 8, 8)
        self._crear_parametro(t, "cura_aislada_min", "Umbral mínimo", 0, 8, 8)
        self._crear_parametro(t, "cura_aislada_peso_ref", "Peso de referencia de la cura", 0.001, 1, 999, False, 3)
        self._crear_texto(t, "cura_aislada")
        self._crear_titulo(t, "Muerte de la cura por sobrepoblación (demasiadas vecinas de cura)")
        self._crear_parametro(t, "cura_satura_base", "Umbral base de vecinas de cura", 0, 8, 8)
        self._crear_parametro(t, "cura_satura_min", "Umbral mínimo", 0, 8, 8)
        self._crear_parametro(t, "cura_satura_peso_ref", "Peso de referencia de la cura", 0.001, 1, 999, False, 3)
        self._crear_texto(t, "cura_satura")
        self._crear_boton_defecto(t, "cura")

        # Si el usuario cambia los pesos, se recalculan los ejemplos numéricos
        self.cancer_weight_entry.bind("<KeyRelease>", lambda e: self.actualizar_resumen_reglas(), add="+")
        self.cure_weight_entry.bind("<KeyRelease>", lambda e: self.actualizar_resumen_reglas(), add="+")

        self.refrescar_controles_reglas()

    def _crear_titulo(self, parent, texto):
        ctk.CTkLabel(parent, text=texto, font=("Arial", 12, "bold")).pack(anchor="w", padx=5, pady=(10, 2))

    def _crear_texto(self, parent, clave):
        """Etiqueta con la explicación matemática de la regla (se actualiza sola)."""
        etiqueta = ctk.CTkLabel(parent, text="", font=("Arial", 10), text_color="#9ca3af",
                                wraplength=700, justify="left", anchor="w")
        etiqueta.pack(anchor="w", padx=10, pady=(2, 0))
        self.textos_reglas[clave] = etiqueta

    def _crear_boton_defecto(self, parent, grupo):
        ctk.CTkButton(
            parent, text="Valores por defecto de esta pestaña",
            fg_color="#b45309", hover_color="#92400e",
            command=lambda: self.restaurar_reglas(grupo)
        ).pack(anchor="e", padx=5, pady=(10, 2))

    def _crear_parametro(self, parent, clave, etiqueta, minimo, maximo, pasos, entero=True, decimales=2):
        """Fila con etiqueta, deslizador y valor numérico para un parámetro de las reglas."""
        fila = ctk.CTkFrame(parent)
        fila.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(fila, text=etiqueta, width=340, anchor="w").pack(side="left", padx=5)
        etiqueta_valor = ctk.CTkLabel(fila, text="", width=60)
        etiqueta_valor.pack(side="right", padx=5)

        def al_mover(valor, clave=clave):
            valor = int(round(valor)) if entero else round(float(valor), decimales)
            REGLAS.poner(clave, valor)
            self._refrescar_valor_param(clave)
            self.actualizar_resumen_reglas()

        deslizador = ctk.CTkSlider(fila, from_=minimo, to=maximo, number_of_steps=pasos, command=al_mover)
        deslizador.pack(side="right", fill="x", expand=True, padx=5)
        self.param_widgets[clave] = (deslizador, etiqueta_valor, entero, decimales)

    def _refrescar_valor_param(self, clave):
        deslizador, etiqueta_valor, entero, decimales = self.param_widgets[clave]
        valor = REGLAS.obtener(clave)
        deslizador.set(valor)
        etiqueta_valor.configure(text=str(valor) if entero else f"{valor:.{decimales}f}")

    def _crear_selector_vecinas(self, parent, clave, titulo):
        """Fila de botones 0-8 (nº de vecinas) con una mini-cuadrícula 3x3 de ejemplo."""
        ctk.CTkLabel(parent, text=titulo, font=("Arial", 12, "bold"),
                     wraplength=700, justify="left").pack(anchor="w", padx=5, pady=(8, 2))

        fila = ctk.CTkFrame(parent)
        fila.pack(fill="x", padx=5)
        botones = []
        for n in range(9):
            boton = ctk.CTkButton(fila, text=str(n), width=48, height=40,
                                  command=lambda n=n: self.alternar_vecinas(clave, n))
            boton.pack(side="left", padx=3, pady=3)
            botones.append(boton)
        self.botones_vecinas[clave] = botones

        vista = ctk.CTkFrame(parent)
        vista.pack(fill="x", padx=5, pady=4)
        lienzo = tk.Canvas(vista, width=100, height=100, bg="#1f1f1f", highlightthickness=0)
        lienzo.pack(side="left", padx=8, pady=4)
        ejemplo = ctk.CTkLabel(vista, text="", wraplength=560, justify="left", anchor="w")
        ejemplo.pack(side="left", padx=8)
        self.vistas_vecinas[clave] = (lienzo, ejemplo)
        self.vecinas_ejemplo[clave] = 3 if clave == "nacimiento" else 2

        self._crear_texto(parent, clave)

    def alternar_vecinas(self, clave, n):
        """Activa o desactiva un nº de vecinas en la regla de nacimiento o supervivencia."""
        conjunto = set(REGLAS.obtener(clave))
        if n in conjunto:
            conjunto.remove(n)
        else:
            conjunto.add(n)
        REGLAS.poner(clave, conjunto)
        self.vecinas_ejemplo[clave] = n
        self.refrescar_selector(clave)
        self.actualizar_resumen_reglas()

    def refrescar_selector(self, clave):
        """Colorea los botones activos (verde) y redibuja la vista previa."""
        activos = REGLAS.obtener(clave)
        for n, boton in enumerate(self.botones_vecinas[clave]):
            if n in activos:
                boton.configure(fg_color="#16a34a", hover_color="#15803d")
            else:
                boton.configure(fg_color="#4b5563", hover_color="#374151")
        self.dibujar_vista_vecinas(clave)

    def dibujar_vista_vecinas(self, clave):
        """Mini-cuadrícula 3x3: la célula central y n vecinas vivas (verdes) de ejemplo."""
        lienzo, ejemplo = self.vistas_vecinas[clave]
        n = self.vecinas_ejemplo[clave]
        lienzo.delete("all")
        posiciones = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1), (2, 2)]
        for indice, (fila, col) in enumerate(posiciones):
            color = "#00FF00" if indice < n else "#000000"
            lienzo.create_rectangle(col * 32 + 3, fila * 32 + 3, col * 32 + 33, fila * 32 + 33,
                                    fill=color, outline="#808080")
        palabra = "vecina viva" if n == 1 else "vecinas vivas"
        if clave == "nacimiento":
            lienzo.create_rectangle(35, 35, 65, 65, fill="#000000", outline="#ffffff", width=2)
            lienzo.create_text(50, 50, text="?", fill="white", font=("Arial", 14, "bold"))
            resultado = "NACE (pasa a viva)" if n in REGLAS.nacimiento else "sigue muerta"
            ejemplo.configure(text=f"Ejemplo: una célula muerta con {n} {palabra} → {resultado}")
        else:
            lienzo.create_rectangle(35, 35, 65, 65, fill="#00FF00", outline="#ffffff", width=2)
            resultado = "SOBREVIVE" if n in REGLAS.supervivencia else "MUERE"
            ejemplo.configure(text=f"Ejemplo: una célula viva con {n} {palabra} → {resultado}")

    def _pesos_actuales(self):
        """Pesos de cáncer y cura escritos en los cuadros de texto (para los ejemplos)."""
        try:
            peso_cancer = max(0.0001, min(1.0, float(self.cancer_weight_var.get())))
        except ValueError:
            peso_cancer = 0.01
        try:
            peso_cura = max(0.0001, min(1.0, float(self.cure_weight_var.get())))
        except ValueError:
            peso_cura = 0.1
        return peso_cancer, peso_cura

    def actualizar_resumen_reglas(self):
        """Actualiza la notación N/S y las explicaciones matemáticas."""
        peso_cancer, peso_cura = self._pesos_actuales()
        textos = REGLAS.textos(peso_cancer, peso_cura)
        self.regla_notacion_label.configure(text=REGLAS.notacion())
        for clave, etiqueta in self.textos_reglas.items():
            etiqueta.configure(text=textos[clave])

    def refrescar_controles_reglas(self):
        """Sincroniza todos los controles con los valores actuales de las reglas."""
        for clave in self.param_widgets:
            self._refrescar_valor_param(clave)
        for clave in self.botones_vecinas:
            self.refrescar_selector(clave)
        self.actualizar_resumen_reglas()

    def restaurar_reglas(self, grupo=None):
        """Vuelve a los valores por defecto (de una pestaña o de todas las reglas)."""
        REGLAS.restaurar(Reglas.GRUPOS[grupo] if grupo else None)
        self.refrescar_controles_reglas()

    def on_window_resize(self, event):
        """Gestiona los cambios de tamaño de la ventana"""
        # Atender solo los cambios de tamaño de la ventana principal
        if event.widget == self.root:
            # Actualizar el tamaño máximo del lienzo según el tamaño de la ventana
            window_width = self.root.winfo_width()
            window_height = self.root.winfo_height()

            # Reservar espacio para controles y gráficos (unos 400 px para gráficos y 200 px para controles)
            available_width = max(300, window_width - 600)
            available_height = max(300, window_height - 300)

            # Actualizar el tamaño máximo del lienzo
            new_max_size = min(available_width, available_height)
            if abs(new_max_size - self.max_canvas_size) > 50:  # Solo actualizar si el cambio es significativo
                self.max_canvas_size = new_max_size

                # Recalcular el tamaño de celda si es necesario
                if self.grid_size * self.cell_size > self.max_canvas_size:
                    self.cell_size = max(1, self.max_canvas_size // self.grid_size)

                    # Actualizar el lienzo y el marco desplazable
                    new_canvas_size = self.grid_size * self.cell_size
                    self.canvas.configure(width=new_canvas_size, height=new_canvas_size)

                    scroll_width = min(new_canvas_size + 40, self.max_canvas_size)
                    scroll_height = min(new_canvas_size + 40, self.max_canvas_size)
                    self.canvas_scroll_frame.configure(width=scroll_width, height=scroll_height)

                    # Actualizar la pantalla
                    self.update_canvas()

    def run(self):
        """Inicia el bucle principal de la interfaz"""
        self.root.mainloop()

if __name__ == "__main__":
    app = ConwayGUI()
    app.run()
