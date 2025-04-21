# -*- coding: utf-8 -*-
"""
Script para analizar programas COBOL, extraer la estructura de llamadas entre párrafos
y las sentencias SQL embebidas. Genera representaciones visuales y textuales del análisis.
"""

# Módulos estándar necesarios
import traceback  # Para manejo de errores detallado
import sys        # Para acceder a argumentos de línea de comandos
import os         # Para manipulación de rutas de archivos
import re         # Para expresiones regulares en el análisis

# Módulo externo necesario (instalar con: pip install graphviz)
from graphviz import Digraph  # Para generación de diagramas

def extraer_sentencias_sql(bloque_sql):
    """
    Extrae las sentencias SQL de un bloque de código SQL.

    Parámetros:
        bloque_sql (str): Texto completo del bloque SQL a analizar

    Retorna:
        list: Lista de tuplas con (tipo_sentencia, objeto_relacionado) encontradas
    """
    sentencias = []

    # Normalizamos el texto
    bloque_sql = bloque_sql.upper()

    # SELECT ... FROM tabla
    for match in re.finditer(r"SELECT .*?FROM\s+(\w+)", bloque_sql, re.IGNORECASE):
        sentencias.append(("SELECT", match.group(1)))

    # INSERT INTO tabla
    for match in re.finditer(r"INSERT\s+INTO\s+(\w+)", bloque_sql, re.IGNORECASE):
        sentencias.append(("INSERT", match.group(1)))

    # UPDATE tabla
    for match in re.finditer(r"UPDATE\s+(\w+)", bloque_sql, re.IGNORECASE):
        sentencias.append(("UPDATE", match.group(1)))

    # DELETE FROM tabla
    for match in re.finditer(r"DELETE\s+FROM\s+(\w+)", bloque_sql, re.IGNORECASE):
        sentencias.append(("DELETE", match.group(1)))

    # OPEN cursor
    for match in re.finditer(r"OPEN\s+(\w+)", bloque_sql, re.IGNORECASE):
        sentencias.append(("OPEN CURSOR", match.group(1)))

    # CLOSE cursor
    for match in re.finditer(r"CLOSE\s+(\w+)", bloque_sql, re.IGNORECASE):
        sentencias.append(("CLOSE CURSOR", match.group(1)))

    # FETCH cursor
    for match in re.finditer(r"FETCH\s+(\w+)", bloque_sql, re.IGNORECASE):
        sentencias.append(("FETCH CURSOR", match.group(1)))

    # COMMIT
    if 'COMMIT' in bloque_sql:
        sentencias.append(("COMMIT", ''))

    # ROLLBACK
    if 'ROLLBACK' in bloque_sql:
        sentencias.append(("ROLLBACK", ''))

    return sentencias

def procesar_bloque_sql(archivo, parrafo_actual, selects_por_parrafo):
    """
    Procesa un bloque SQL completo (desde EXEC SQL hasta END-EXEC).
    
    Parámetros:
        archivo (file): Objeto archivo abierto que se está analizando
        parrafo_actual (str): Nombre del párrafo COBOL donde se encontró el SQL
        selects_por_parrafo (dict): Diccionario para acumular los resultados
        
    Efecto:
        Modifica selects_por_parrafo añadiendo las sentencias encontradas
    """
    bloque_sql = []
    
    # Leer líneas hasta encontrar END-EXEC
    for linea in archivo:
        bloque_sql.append(linea.strip())
        if 'END-EXEC' in linea.upper():
            break
    
    # Unir todo el bloque y convertirlo a mayúsculas
    bloque_completo = ' '.join(bloque_sql).upper()
    
    # Extraer y almacenar las sentencias SQL encontradas
    for tipo, tabla in extraer_sentencias_sql(bloque_completo):
        selects_por_parrafo.setdefault(parrafo_actual, [])
        selects_por_parrafo[parrafo_actual].append(f"{tipo} ... {tabla}")

def es_linea_ignorable(linea):
    """
    Determina si una línea del código COBOL puede ser ignorada en el análisis.
    
    Parámetros:
        linea (str): Línea de código a evaluar
        
    Retorna:
        bool: True si la línea puede ignorarse, False si debe procesarse
    """
    # Línea vacía o comentario (columna 7 = '*' en COBOL)
    return not linea or (len(linea) >= 7 and linea[6] == '*')

def detectar_parrafo(linea):
    """
    Detecta si una línea marca el inicio de un nuevo párrafo en COBOL.
    
    Parámetros:
        linea (str): Línea de código a evaluar
        
    Retorna:
        str/None: Nombre del párrafo si se detecta, None si no
    """
    stripped = linea.strip()
    
    # En COBOL, los párrafos terminan con punto
    if stripped.endswith('.') and not stripped.upper().startswith('PERFORM'):
        posible_parrafo = stripped.rstrip('.')
        
        # Excluir ciertas palabras clave que no son nombres de párrafo
        if posible_parrafo.upper() not in ['VARYING', 'UNTIL', 'WITH']:
            return posible_parrafo
    return None

def detectar_perform(linea):
    """
    Detecta instrucciones PERFORM que indican llamadas entre párrafos.
    
    Parámetros:
        linea (str): Línea de código a evaluar
        
    Retorna:
        str/None: Nombre del párrafo destino si se detecta PERFORM, None si no
    """
    if 'PERFORM' in linea.upper():
        partes = linea.strip().upper().split()
        try:
            # Buscar la posición de PERFORM en la línea
            idx = partes.index('PERFORM')
            destino = partes[idx + 1].rstrip('.')
            
            # Excluir ciertas palabras clave que no son nombres de párrafo
            if destino in ['VARYING', 'UNTIL', 'WITH']:
                return None
            return destino
        except (IndexError, ValueError):
            return None
    return None

def filtrar_desde_parrafo_inicio(llamadas, parrafo_inicio):
    """
    Filtra el diccionario de llamadas para mostrar solo los párrafos accesibles
    desde el párrafo inicial especificado.
    
    Parámetros:
        llamadas (dict): Diccionario completo de relaciones entre párrafos
        parrafo_inicio (str): Párrafo desde el cual comenzar el análisis
        
    Retorna:
        dict: Subconjunto filtrado del diccionario original
    """
    if parrafo_inicio not in llamadas:
        print(f"El parrafo '{parrafo_inicio}' no existe en el archivo")
        return {}

    # Inicializar resultado con el párrafo de inicio
    resultado = {parrafo_inicio: llamadas.get(parrafo_inicio, [])}
    
    # Búsqueda en profundidad para encontrar todos los párrafos accesibles
    for origen, destinos in list(llamadas.items()):
        pendientes = destinos.copy()
        while pendientes:
            destino = pendientes.pop()
            if destino in resultado:
                continue
            if destino in llamadas:
                resultado[origen].append(destino)
            else:
                pendientes.extend(llamadas.get(destino, []))
    return resultado

def obtener_parrafos_accesibles(llamadas, parrafo_inicio):
    """
    Obtiene todos los párrafos accesibles desde un párrafo inicial dado.
    
    Parámetros:
        llamadas (dict): Diccionario de relaciones entre párrafos
        parrafo_inicio (str): Párrafo desde el cual comenzar
        
    Retorna:
        set: Conjunto de nombres de párrafos accesibles
    """
    accesibles = set()
    pendientes = [parrafo_inicio or '__START__']
    
    # Búsqueda en amplitud para encontrar todos los párrafos accesibles
    while pendientes:
        actual = pendientes.pop()
        if actual in accesibles:
            continue
        accesibles.add(actual)
        pendientes.extend(llamadas.get(actual, []))
    return accesibles

def analizar_cobol(ruta_archivo, parrafo_inicio=None, analizar_sql=False):
    """
    Función principal que analiza un archivo COBOL y extrae su estructura.
    
    Parámetros:
        ruta_archivo (str): Ruta al archivo COBOL a analizar
        parrafo_inicio (str): Opcional, párrafo desde el cual comenzar
        analizar_sql (bool): Si es True, extrae y analiza sentencias SQL
        
    Retorna:
        tuple: (diccionario_llamadas, bloques_exec_sql, selects_por_parrafo)
    """
    llamadas = {}  # Almacenará las relaciones PERFORM entre párrafos
    selects_por_parrafo = {}  # Almacenará las sentencias SQL por párrafo
    en_procedure_division = False  # Flag para saber si estamos en PROCEDURE DIVISION
    parrafo_actual = '__START__'  # Párrafo actual durante el análisis
    bloque_sql_count = 0  # Contador de bloques EXEC SQL encontrados

    try:
        with open(ruta_archivo, 'r', encoding='latin-1') as archivo:
            for linea in archivo:
                # Saltar líneas ignorables (comentarios, vacías)
                if es_linea_ignorable(linea):
                    continue

                # Procesar bloques SQL si está activado el análisis SQL
                if analizar_sql and 'EXEC SQL' in linea.upper():
                    bloque_sql_count += 1
                    procesar_bloque_sql(archivo, parrafo_actual, selects_por_parrafo)
                    continue

                # Marcar cuando entramos en PROCEDURE DIVISION
                if 'PROCEDURE DIVISION' in linea.upper():
                    en_procedure_division = True
                    continue

                # Ignorar todo antes de PROCEDURE DIVISION
                if not en_procedure_division:
                    continue

                # Detectar inicio de nuevos párrafos
                nuevo_parrafo = detectar_parrafo(linea)
                if nuevo_parrafo:
                    parrafo_actual = nuevo_parrafo
                    if parrafo_actual not in llamadas:
                        llamadas[parrafo_actual] = []
                    continue

                # Detectar llamadas PERFORM dentro del párrafo actual
                if parrafo_actual:
                    destino = detectar_perform(linea)
                    if destino:
                        llamadas.setdefault(parrafo_actual, []).append(destino)

        # Filtrar por párrafo inicial si se especificó
        if parrafo_inicio:
            llamadas = filtrar_desde_parrafo_inicio(llamadas, parrafo_inicio)

        # Obtener solo los párrafos accesibles desde el inicio
        accesibles = obtener_parrafos_accesibles(llamadas, parrafo_inicio)
        llamadas = {k: v for k, v in llamadas.items() if k in accesibles or k == '__START__'}
        
        # Filtrar también los SQL si estamos analizándolos
        if analizar_sql:
            selects_por_parrafo = {k: v for k, v in selects_por_parrafo.items() if k in accesibles or k == '__START__'}
        else:
            selects_por_parrafo = {}

    except Exception as e:
        print("Se ha producido un error al analizar el archivo COBOL:")
        traceback.print_exc()
        return {}, 0, {}

    return llamadas, bloque_sql_count, selects_por_parrafo

def imprimir_arbol_llamadas(diccionario, selects_por_parrafo, nodo='', nivel=0, visitados=None, archivo=None):
    """
    Imprime o guarda en archivo la jerarquía de llamadas en formato de árbol.
    
    Parámetros:
        diccionario (dict): Relaciones entre párrafos
        selects_por_parrafo (dict): Sentencias SQL por párrafo
        nodo (str): Nodo actual en la recursión
        nivel (int): Nivel de anidamiento actual
        visitados (set): Nodos ya visitados (para evitar ciclos)
        archivo (file): Objeto archivo donde escribir (si es None, imprime a consola)
    """
    if not nodo:
        if diccionario:
            nodo = next(iter(diccionario))
        else:
            salida = "Diccionario vacio. No hay llamadas que mostrar.\n"
            print(salida)
            if archivo: archivo.write(salida)
            return

    if visitados is None:
        visitados = set()

    # Formatear línea con indentación según nivel
    indent = '   ' * nivel
    linea = f"{indent}{nodo}"
    print(linea)
    if archivo: archivo.write(linea + "\n")

    visitados.add(nodo)

    # Mostrar sentencias SQL asociadas al párrafo si existen
    if nodo in selects_por_parrafo:
        for sel in selects_por_parrafo[nodo]:
            linea = f"{indent}   - {sel}"
            print(linea)
            if archivo: archivo.write(linea + "\n")

    # Recursión para los párrafos llamados desde este
    for hijo in diccionario.get(nodo, []):
        if hijo not in visitados:
            imprimir_arbol_llamadas(diccionario, selects_por_parrafo, hijo, nivel + 1, visitados.copy(), archivo)

def guardar_arbol_llamadas(diccionario, selects_por_parrafo, nombre_archivo_salida):
    """
    Guarda la jerarquía de llamadas en un archivo de texto.
    
    Parámetros:
        diccionario (dict): Relaciones entre párrafos
        selects_por_parrafo (dict): Sentencias SQL por párrafo
        nombre_archivo_salida (str): Nombre base para el archivo de salida
        
    Retorna:
        str: Nombre del archivo generado
    """
    archivo_salida = f"{nombre_archivo_salida}_jerarquia.txt"
    with open(archivo_salida, 'w', encoding='utf-8') as f:
        imprimir_arbol_llamadas(diccionario, selects_por_parrafo, archivo=f)
    print(f"Jerarquia de llamadas guardada en: {archivo_salida}")
    return archivo_salida

def generar_grafo(diccionario, selects_por_parrafo, archivo_salida, analizar_sql=False):
    """
    Genera un diagrama visual de las llamadas entre párrafos y sentencias SQL.
    
    Parámetros:
        diccionario (dict): Relaciones entre párrafos
        selects_por_parrafo (dict): Sentencias SQL por párrafo
        archivo_salida (str): Nombre base para el archivo de salida
        analizar_sql (bool): Si es True, incluye nodos para sentencias SQL
    """
    # Crear objeto Digraph de Graphviz
    dot = Digraph(comment='Llamadas COBOL', format='pdf', engine='dot')
    dot.attr(dpi='300')  # Alta resolución
    dot.attr('node', shape='box', style='filled', fontname='Helvetica', fontsize='10')

    # Estructuras para el recorrido del grafo
    visitados = set()
    niveles = {}
    contador = [1]  # Contador para numerar las llamadas
    orden_llamadas = {}

    def asignar_niveles(nodo, nivel=0):
        """
        Función interna para asignar niveles a los nodos (párrafos) recursivamente.
        """
        if nodo in visitados:
            return
        visitados.add(nodo)
        niveles[nodo] = nivel
        for hijo in diccionario.get(nodo, []):
            orden_llamadas[(nodo, hijo)] = contador[0]
            contador[0] += 1
            asignar_niveles(hijo, nivel + 1)

    # Determinar nodo raíz (__START__ o el primer párrafo)
    nodo_raiz = '__START__'
    if nodo_raiz not in diccionario:
        nodo_raiz = next(iter(diccionario))
    asignar_niveles(nodo_raiz)

    # Organizar nodos por nivel para alinearlos en el gráfico
    niveles_invertido = {}
    for nodo, nivel in niveles.items():
        niveles_invertido.setdefault(nivel, []).append(nodo)

    # Crear nodos del gráfico con colores según su tipo
    for nivel in sorted(niveles_invertido):
        with dot.subgraph() as s:
            s.attr(rank='same')  # Mantener nodos del mismo nivel alineados
            for nodo in niveles_invertido[nivel]:
                color = 'lightblue'  # Color normal para párrafos
                if analizar_sql and nodo in selects_por_parrafo:
                    color = 'lightgreen'  # Color para párrafos con SQL
                s.node(nodo, style='filled', fillcolor=color)

    # Añadir las relaciones (edges) entre párrafos
    for (origen, destino), numero in orden_llamadas.items():
        dot.edge(origen, destino, color='blue', style='solid', arrowsize='0.5', label=str(numero))

    # Añadir nodos para sentencias SQL si está activado
    if analizar_sql:
        for parrafo, selects in selects_por_parrafo.items():
            for idx, sel in enumerate(selects):
                nodo_select = f"{parrafo}_SQL_{idx+1}"
                dot.node(nodo_select, label=sel, shape='note', style='filled', fillcolor='yellow')
                dot.edge(parrafo, nodo_select, style='dashed', color='orange')

    # Generar el archivo PDF
    dot.render(archivo_salida, cleanup=True)
    print(f"Grafo generado: {archivo_salida}.pdf")
    #++++++++++++++++++++++++++++++++
    # Renderizar el archivo .pdf
    pdf_path = dot.render(filename=f"{archivo_salida}.pdf", format='pdf', cleanup=True)

    # Abrir el PDF automáticamente
    os.startfile(pdf_path)  # Solo funciona en Windows
    #++++++++++++++++++++++++++++++++

if __name__ == "__main__":
    """
    Punto de entrada principal del script.
    Maneja argumentos de línea de comandos e interfaz de usuario.
    """
    analizar_sql = False  # Por defecto no analizar SQL
    parrafo_inicio = None  # Por defecto comenzar desde el principio
    
    # Procesar argumentos de línea de comandos
    if len(sys.argv) > 1:
        ruta_del_programa_cobol = sys.argv[1]
        
        # Verificar si se pasó el parámetro SQL o párrafo inicial
        if len(sys.argv) > 2:
            for arg in sys.argv[2:]:
                if arg.upper() == 'SQL':
                    analizar_sql = True
                elif not arg.upper() == 'SQL':
                    parrafo_inicio = arg
    else:
        # Modo interactivo si no hay argumentos
        ruta_del_programa_cobol = input("Por favor, ingresa la ruta del programa COBOL: ")
        respuesta = input("¿Deseas analizar sentencias SQL? (s/n): ").lower()
        analizar_sql = respuesta == 's'
        if not analizar_sql:
            parrafo_inicio = input("Si deseas comenzar desde un parrafo especifico, ingresalo (de lo contrario, deja en blanco): ")

    # Ejecutar análisis principal
    diccionario_llamadas, bloques_exec_sql, selects_por_parrafo = analizar_cobol(
        ruta_del_programa_cobol, 
        parrafo_inicio, 
        analizar_sql
    )

    # Mostrar resultados básicos en consola
    print(diccionario_llamadas)
    if analizar_sql:
        print(f"Total de bloques EXEC SQL encontrados: {bloques_exec_sql}")
    print("Relaciones de llamadas:")
    imprimir_arbol_llamadas(diccionario_llamadas, selects_por_parrafo)

    # Generar nombre base para archivos de salida
    nombre_archivo_salida = os.path.splitext(ruta_del_programa_cobol)[0]
    
    # Guardar siempre el archivo de texto con la jerarquía
    archivo_txt = guardar_arbol_llamadas(diccionario_llamadas, selects_por_parrafo, nombre_archivo_salida)
    
    # Generar el gráfico PDF
    generar_grafo(diccionario_llamadas, selects_por_parrafo, nombre_archivo_salida, analizar_sql)