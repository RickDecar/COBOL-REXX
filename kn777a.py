"""
analizador de uso de tablas SQL en codigo legacy
"""
import csv
import os
import re
from collections import defaultdict
from graphviz import Digraph

# === Estructuras de datos principales ===

# Almacena el uso de tablas → programas → operaciones SQL (como SELECT, INSERT...)
uso_por_tabla = defaultdict(lambda: defaultdict(set))

# Almacena relaciones entre tablas detectadas por JOINs como ((tabla1, campo1), (tabla2, campo2))
relaciones_detectadas = set()

# === Expresiones regulares para análisis ===

# Extrae bloques EXEC SQL ... END-EXEC
sql_regex = re.compile(r"EXEC SQL(.*?)END-EXEC", re.DOTALL | re.IGNORECASE)

# Detecta operaciones básicas
operaciones = {
    'SELECT': re.compile(r"\bSELECT\b.*?\bFROM\b\s+(\w+)", re.IGNORECASE),
    'INSERT': re.compile(r"\bINSERT\s+INTO\b\s+(\w+)", re.IGNORECASE),
    'UPDATE': re.compile(r"\bUPDATE\b\s+(\w+)", re.IGNORECASE),
    'DELETE': re.compile(r"\bDELETE\s+FROM\b\s+(\w+)", re.IGNORECASE),
}

# Detecta JOINs del tipo: FROM t1 a1 JOIN t2 a2 ON a1.campo = a2.campo
join_regex = re.compile(r"""
    FROM\s+(\w+)\s+(\w+)?           # tabla1 alias1 (opcional)
    .*?JOIN\s+(\w+)\s+(\w+)?        # tabla2 alias2 (opcional)
    \s+ON\s+([\w\.]+)\s*=\s*([\w\.]+)
""", re.IGNORECASE | re.DOTALL | re.VERBOSE)

# Detecta JOINs implícitos: FROM t1, t2 WHERE t1.campo = t2.campo
where_join_regex = re.compile(r"""
    FROM\s+([\w\s,]+?)              # listado de tablas separadas por coma
    \s+WHERE\s+([\w\.]+)\s*=\s*([\w\.]+)
""", re.IGNORECASE | re.DOTALL | re.VERBOSE)

# === Funciones auxiliares ===

def normaliza_relacion(c1, c2, t1, a1, t2, a2):
    """
    Convierte una relación (campos de tablas o alias) en forma normalizada.
    """
    def resolver(tabla, alias, campo):
        if '.' in campo:
            pref, campo = campo.split('.')
            # Si el prefijo coincide con el alias, se resuelve como la tabla correspondiente
            if alias and pref.upper() == alias.upper():
                return tabla.upper(), campo.upper()
            else:
                return pref.upper(), campo.upper()
        return tabla.upper(), campo.upper()

    lado1 = resolver(t1, a1, c1)
    lado2 = resolver(t2, a2, c2)
    return tuple(sorted([lado1, lado2]))  # Orden alfabético para evitar duplicados

def detectar_joins(contenido):
    """
    Detecta JOINs explícitos e implícitos en el bloque SQL.
    """
    for match in join_regex.finditer(contenido):
        t1, a1, t2, a2, campo1, campo2 = match.groups()
        relaciones_detectadas.add(normaliza_relacion(campo1, campo2, t1, a1, t2, a2))

    for match in where_join_regex.finditer(contenido):
        tablas, campo1, campo2 = match.groups()
        tablas_split = [t.strip() for t in tablas.split(',')]
        if len(tablas_split) >= 2:
            t1, t2 = tablas_split[0], tablas_split[1]
            relaciones_detectadas.add(normaliza_relacion(campo1, campo2, t1, None, t2, None))

def analizar_programa(path_archivo):
    """
    Lee un archivo COBOL, extrae bloques SQL y analiza operaciones y relaciones.
    """
    with open(path_archivo, 'r', encoding='utf-8', errors='ignore') as f:
        contenido = f.read()

    nombre_programa = os.path.basename(path_archivo)

    for bloque_sql in sql_regex.findall(contenido):
        detectar_joins(bloque_sql)
        for op, patron in operaciones.items():
            for match in patron.findall(bloque_sql):
                tabla = match.upper()
                uso_por_tabla[tabla][nombre_programa].add(op)

def recorrer_directorio(directorio):
    """
    Recorre recursivamente un directorio buscando archivos COBOL (.cbl).
    """
    print(f"directorio a analizar {directorio}")
    for root, _, files in os.walk(directorio):
        for file in files:
            if file.lower().endswith('.cbl'):
                print(f"📂 Analizando: {file}")  # ← debug aquí
                analizar_programa(os.path.join(root, file))
            else:
                print(f"📂 descartando: {file}")  # ← debug aquí

def agregar_relaciones(dot):
    """
    Agrega al grafo las relaciones entre tablas como líneas punteadas.
    """
    for ((t1, c1), (t2, c2)) in relaciones_detectadas:
        dot.edge(t1, t2, label=f"{c1} ↔ {c2}", style="dashed", color="gray")

def generar_grafico(output_file='uso_tablas'):
    """
    Genera un archivo gráfico con la estructura: tabla → programa → operación
    y añade relaciones entre tablas si las hay.
    """
    dot = Digraph(comment='Relación Tablas - Programas - Operaciones', format='png')
    dot.attr(rankdir='LR', fontsize='10')

    # Agrega nodos y relaciones de uso de tablas
    for tabla, programas in uso_por_tabla.items():
        dot.node(tabla, shape='box', style='filled', fillcolor='lightblue')

        for programa, ops in programas.items():
            prog_node = f"{tabla}_{programa}"
            dot.node(prog_node, label=programa, shape='ellipse', style='filled', fillcolor='lightyellow')
            dot.edge(tabla, prog_node)

            for op in ops:
                op_node = f"{prog_node}_{op}"
                dot.node(op_node, label=op, shape='note', style='filled', fillcolor='lightgreen')
                dot.edge(prog_node, op_node)

    # Agrega relaciones entre tablas (JOINs)
    agregar_relaciones(dot)

    # Genera el gráfico y lo abre
    dot.render(output_file, view=True)
    print(f"Gráfico generado: {output_file}.png")

def exportar_a_csv(diccionario, archivo_salida="analisis_sql.csv"):
    with open(archivo_salida, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Tabla", "Programa", "Operaciones"])
        
        for tabla, programas in diccionario.items():
            for programa, operaciones in programas.items():
                writer.writerow([tabla, programa, ", ".join(sorted(operaciones))])

    print(f"✅ CSV generado: {archivo_salida}")


# === EJECUCIÓN ===

# ⚠️ Reemplaza esto con el path real de tus programas COBOL
directorio = "c:/aina"

# Paso 1: analizar los programas
recorrer_directorio(directorio)

# Paso 2: generar el gráfico
generar_grafico("grafico_tablas_y_joins")

# Paso 3: exportar a .csv
exportar_a_csv(uso_por_tabla)

