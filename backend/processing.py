# processing.py

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Tuple, List
# Importar unidecode para quitar tildes/acentos
try:
    from unidecode import unidecode
except ImportError:
    print("Error: La librería 'unidecode' no está instalada.")
    print("Por favor, instálala ejecutando: pip install unidecode")
    # Alternativa simple (puede no cubrir todos los casos):
    def unidecode(text):
        import unicodedata
        return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    print("Usando alternativa simple para quitar acentos.")


# --- Constantes ---
# Nombres de columnas para el archivo auxiliar SIESA
AUXILIAR_FECHA = 'Fecha'
AUXILIAR_DOCUMENTO = 'Documento'
AUXILIAR_CO = 'C.O.'
AUXILIAR_UN = 'U.N.'
AUXILIAR_DESC_TRANSACCION = 'descripcion_transaccion' # Nombre estándar que queremos al final
AUXILIAR_TEXT1 = 'text1'
AUXILIAR_TEXT2 = 'text2'
AUXILIAR_TEXT3 = 'text3'
AUXILIAR_SALDO_INICIAL = 'saldo_inicial'
AUXILIAR_DEBITO = 'debito' # Nombre estándar singular sin tilde
AUXILIAR_CREDITO = 'credito' # Nombre estándar singular sin tilde
AUXILIAR_SALDO_FINAL = 'saldo_final'

# Índice esperado para la columna de descripción si el nombre no coincide
AUXILIAR_DESC_INDEX = 4 # Quinta columna (índice basado en 0)

# Columnas clave para identificar la cabecera en SIESA (se limpiarán antes de comparar)
AUXILIAR_COLUMNAS_CLAVE_CABECERA = [AUXILIAR_FECHA, AUXILIAR_DOCUMENTO, AUXILIAR_DEBITO, AUXILIAR_CREDITO]
# Columnas finales después de transformar SIESA (estos son los nombres estándar)
AUXILIAR_COLUMNAS_FINALES = [
    'fecha_norm', 'documento_auxiliar', 'descripcion_auxiliar',
    AUXILIAR_DEBITO, AUXILIAR_CREDITO
]


# Nombres de columnas para el extracto Bancolombia (CSV - 9 Columnas)
EXTRACTO_COLUMNAS_CSV_9COLS_CORRECTO = [
    'cuenta_raw', 'codigo_trans_raw', 'col_3_ignorar', 'fecha_raw',
    'col_5_ignorar', 'movimiento_raw', 'codigo_desc_raw', 'descripcion_raw', 'col_9_ignorar'
]
EXTRACTO_COLUMNAS_A_ELIMINAR_9COLS_CORRECTO = [
    'cuenta_raw', 'codigo_trans_raw', 'col_3_ignorar', 'col_5_ignorar',
    'codigo_desc_raw', 'col_9_ignorar'
]
EXTRACTO_COLUMNAS_REQUERIDAS_FUENTE = ['fecha_raw', 'descripcion_raw', 'movimiento_raw']
EXTRACTO_COLUMNAS_FINALES = ['fecha_norm', 'movimiento', 'descripcion_extracto']
EXTRACTO_VALORES_A_EXCLUIR_DESC = ['SALDO DIA', 'SALDO FINAL', 'SALDO INICIAL']

# Nombres de columnas para movimientos Bancolombia (CSV)
MOVIMIENTO_CUENTA = 'cuenta_bancaria'
MOVIMIENTO_FECHA = 'fecha'
MOVIMIENTO_VALOR = 'movimiento'
MOVIMIENTO_DESC = 'descripcion_movimiento'
MOVIMIENTO_COLUMNAS_FIJAS_INDICES = [0, 3, 5, 7]
MOVIMIENTO_COLUMNAS_NOMBRES = [
    MOVIMIENTO_CUENTA, MOVIMIENTO_FECHA, MOVIMIENTO_VALOR, MOVIMIENTO_DESC
]

# Columnas comunes para conciliación
FECHA_CONCILIACION = 'fecha_norm' # Asegúrate que esta definición esté aquí y sea global
MOVIMIENTO_CONCILIACION = 'movimiento' # Asegúrate que esta definición esté aquí y sea global
CONTADOR_CONCILIACION = 'contador'

# --- Funciones de Formateo ---

def clean_text(text: str) -> str:
    """Limpia texto: convierte a minúsculas, quita acentos y espacios."""
    if not isinstance(text, str):
        text = str(text)
    cleaned = unidecode(text)
    cleaned = cleaned.lower().strip()
    return cleaned

def format_currency(value: any) -> float:
    """
    Convierte un valor a float, manejando formato monetario.
    Asume que '.' es el separador decimal y ',' (opcional) es el separador de miles.
    """
    if pd.isna(value):
        return 0.0
    try:
        if isinstance(value, str):
            # 1. Quitar símbolo de moneda ($) y espacios extra
            cleaned_value = value.replace('$', '').strip()
            # 2. Quitar separadores de miles (comas)
            cleaned_value = cleaned_value.replace(',', '')
            # 3. Ahora el string debe tener solo números, un posible signo '-'
            #    y el punto '.' como decimal. float() lo entiende directamente.
            #    ¡NO quitar el punto!
            return float(cleaned_value)
        else:
            # Si ya es un número (int, float), intentar convertir a float
            return float(value)
    except (ValueError, TypeError) as e:
        # Imprimir advertencia si la conversión falla
        print(f"Advertencia: No se pudo formatear el valor '{value}' como moneda: {e}")
        return 0.0


def format_date_robust(date_value: any) -> Optional[datetime.date]:
    """Intenta convertir un valor a fecha (objeto date)."""
    if pd.isna(date_value) or not date_value:
        return None
    if isinstance(date_value, datetime):
        return date_value.date()
    # Manejo explícito de numpy.datetime64
    if isinstance(date_value, np.datetime64):
        # Convertir a Timestamp de Pandas primero para manejo seguro
        try:
            ts = pd.Timestamp(date_value)
            # pd.NaT (Not a Time) es el equivalente de NaN para datetime
            if pd.isna(ts):
                return None
            return ts.to_pydatetime().date()
        except Exception as e:
             print(f"Advertencia: No se pudo convertir np.datetime64 '{date_value}' a fecha: {e}")
             return None


    # Intentar con pd.to_datetime (más flexible)
    try:
        # Especificar dayfirst=True si el formato DD/MM/YYYY es común
        dt = pd.to_datetime(date_value, errors='coerce', dayfirst=True)
        if pd.isna(dt):
            # Intentar formatos específicos si to_datetime falla
            date_str = str(date_value).strip()
            # Ejemplo: Formato sin separadores DDMMAAAA o YYYYMMDD
            if len(date_str) == 8 and date_str.isdigit():
                try:
                    # Intentar DDMMAAAA primero si es más común en tus datos
                    dt = datetime.strptime(date_str, '%d%m%Y')
                except ValueError:
                    try:
                        dt = datetime.strptime(date_str, '%Y%m%d')
                    except ValueError:
                        dt = None # No coincide con formatos comunes sin separador
            # Añadir más formatos aquí si son necesarios, ej. 'YYYY-MM-DD', 'MM/DD/YYYY', etc.
            # elif ... :

        # Si después de todo, dt sigue siendo NaT (o None si fallaron los strptime)
        if pd.isna(dt):
            # print(f"Advertencia: No se pudo parsear la fecha '{date_value}' a ningún formato conocido.")
            return None

        # Si pd.to_datetime funcionó, devolvió un Timestamp, convertir a date
        if isinstance(dt, pd.Timestamp): # O datetime.datetime si strptime funcionó
             return dt.date()
        elif isinstance(dt, datetime): # Si strptime funcionó
             return dt.date()
        else:
             # Caso inesperado, ¿qué tipo devolvió pd.to_datetime?
             print(f"Advertencia: Tipo inesperado '{type(dt)}' después de parsear fecha '{date_value}'.")
             return None

    except Exception as e:
        print(f"Error inesperado al formatear fecha '{date_value}': {e}")
        return None

# --- Funciones de Procesamiento de Archivos ---

def transform_siesa_auxiliary(file_path: str) -> Optional[pd.DataFrame]:
    """
    Lee y transforma un archivo auxiliar de SIESA (Excel), con detección
    flexible de cabecera y selección/renombrado robusto de columnas.

    Args:
        file_path: Ruta al archivo Excel.

    Returns:
        Un DataFrame de pandas con las columnas finales o None si ocurre un error.
    """
    try:
        # Leer todas las hojas si no se especifica una
        # O especificar sheet_name=0 para leer solo la primera
        # Usar dtype=str para leer todo como texto inicialmente y evitar conversiones automáticas
        df_excel = pd.read_excel(file_path, header=None, sheet_name=None, dtype=str)

        if not isinstance(df_excel, dict):
             # Si solo hay una hoja, read_excel podría no devolver un dict
             if isinstance(df_excel, pd.DataFrame):
                 df_auxiliar = df_excel # Trabaja con el único DataFrame leído
             else:
                 raise ValueError("Formato inesperado al leer el archivo Excel. Se esperaba un DataFrame o un diccionario de DataFrames.")
        elif not df_excel:
             raise ValueError(f"El archivo Excel '{file_path}' está vacío o no contiene hojas.")
        else:
             # Si hay múltiples hojas, decidir cuál usar.
             # Por defecto, usar la primera hoja. Cambiar si es necesario.
             first_sheet_name = list(df_excel.keys())[0]
             print(f"Info: Archivo Excel con múltiples hojas. Usando la primera hoja: '{first_sheet_name}'")
             df_auxiliar = df_excel[first_sheet_name]

        df_auxiliar = df_auxiliar.dropna(how='all').reset_index(drop=True)
        # Reemplazar valores que son solo espacios en blanco con NaN para limpieza
        df_auxiliar.replace(r'^\s*$', pd.NA, regex=True, inplace=True)
        df_auxiliar = df_auxiliar.dropna(how='all').reset_index(drop=True)


        # --- Detección de Cabecera Flexible ---
        header_row_index = -1
        detected_columns = []
        fecha_clean = clean_text(AUXILIAR_FECHA)
        doc_clean = clean_text(AUXILIAR_DOCUMENTO)
        debito_clean = clean_text(AUXILIAR_DEBITO)
        credito_clean = clean_text(AUXILIAR_CREDITO)
        debitos_clean = 'debitos' # Variante común
        creditos_clean = 'creditos' # Variante común
        desc_clean = clean_text(AUXILIAR_DESC_TRANSACCION)

        max_rows_to_scan = 50 # Aumentar si la cabecera puede estar más abajo
        print(f"Info: Buscando cabecera SIESA en las primeras {max_rows_to_scan} filas...")

        for i, row in df_auxiliar.head(max_rows_to_scan).iterrows():
            # Limpiar los valores de la fila para comparación insensible
            # Ignorar valores NaN al buscar las cabeceras
            row_values_clean = {clean_text(v) for v in row.values if pd.notna(v)}

            # Verificar presencia de columnas clave (limpiadas)
            has_fecha = fecha_clean in row_values_clean
            has_doc = doc_clean in row_values_clean
            # Buscar cualquiera de las variantes de débito/crédito
            has_debito_variant = debito_clean in row_values_clean or debitos_clean in row_values_clean
            has_credito_variant = credito_clean in row_values_clean or creditos_clean in row_values_clean

            # Si encontramos todas las claves en la fila actual
            if has_fecha and has_doc and has_debito_variant and has_credito_variant:
                header_row_index = i
                # Tomar los valores originales de esa fila como nombres de columna
                # Si hay NaN, generar un nombre único para evitar problemas
                detected_columns = [str(v).strip() if pd.notna(v) else f'unnamed_{j}' for j, v in enumerate(df_auxiliar.iloc[i])]
                print(f"Info: Cabecera detectada en fila {i} del Excel. Columnas detectadas (originales): {detected_columns}")
                break # Salir del bucle una vez encontrada la cabecera

        if header_row_index == -1:
            raise ValueError(f"No se encontró una fila de cabecera válida que contenga '{AUXILIAR_FECHA}', '{AUXILIAR_DOCUMENTO}', y variantes de '{AUXILIAR_DEBITO}'/'{AUXILIAR_CREDITO}' (limpiados) en las primeras {max_rows_to_scan} filas de {file_path}.")

        # Asignar cabecera y eliminar filas anteriores/basura
        df_auxiliar.columns = detected_columns
        df_data = df_auxiliar.iloc[header_row_index + 1:].reset_index(drop=True) # DataFrame solo con datos

        # Eliminar filas donde todas las columnas esenciales sean NaN (probablemente filas vacías o de totales)
        essential_col_names_orig = [col for col in detected_columns if clean_text(col) in [fecha_clean, doc_clean, debito_clean, debitos_clean, credito_clean, creditos_clean]]
        if not essential_col_names_orig:
             print("Advertencia: No se pudieron identificar nombres originales de columnas esenciales para filtrar filas vacías.")
        else:
             # Asegurarse de que los nombres de columnas existan antes de usarlos en dropna
             cols_to_check_for_na = [col for col in essential_col_names_orig if col in df_data.columns]
             if cols_to_check_for_na:
                  original_rows_before_na_drop = len(df_data)
                  df_data = df_data.dropna(subset=cols_to_check_for_na, how='all')
                  rows_dropped = original_rows_before_na_drop - len(df_data)
                  if rows_dropped > 0:
                       print(f"Info: Se eliminaron {rows_dropped} filas donde todas las columnas esenciales ({cols_to_check_for_na}) eran NaN.")
             else:
                  print("Advertencia: Las columnas esenciales identificadas no existen en el DataFrame de datos.")


        if df_data.empty:
            print(f"Advertencia: No quedaron filas de datos válidas en {file_path} después de eliminar filas de cabecera y vacías.")
            return None

        # --- Identificar Nombres Originales de Columnas Necesarias ---
        # Crear un mapeo de nombre limpio a nombre original detectado
        col_map_clean_to_original = {clean_text(col): col for col in detected_columns if isinstance(col, str)}

        fecha_col_orig = col_map_clean_to_original.get(fecha_clean)
        doc_col_orig = col_map_clean_to_original.get(doc_clean)
        # Buscar débito por nombre limpio 'debito' o 'debitos'
        debito_col_orig = col_map_clean_to_original.get(debito_clean, col_map_clean_to_original.get(debitos_clean))
        # Buscar crédito por nombre limpio 'credito' o 'creditos'
        credito_col_orig = col_map_clean_to_original.get(credito_clean, col_map_clean_to_original.get(creditos_clean))
        # Buscar descripción por nombre limpio esperado
        desc_col_orig_from_name = col_map_clean_to_original.get(desc_clean)
        desc_col_orig_from_index = None
        desc_col_final_source = None # Guardará el nombre original de la columna de descripción a usar

        if desc_col_orig_from_name and desc_col_orig_from_name in df_data.columns:
            desc_col_final_source = desc_col_orig_from_name
            print(f"Info: Usando columna '{desc_col_final_source}' para descripción (encontrada por nombre '{desc_clean}').")
        elif len(detected_columns) > AUXILIAR_DESC_INDEX and detected_columns[AUXILIAR_DESC_INDEX] in df_data.columns:
            # Si no se encontró por nombre, intentar por índice si existe
            desc_col_orig_from_index = detected_columns[AUXILIAR_DESC_INDEX]
            desc_col_final_source = desc_col_orig_from_index
            print(f"Info: No se encontró '{desc_clean}' por nombre, usando columna en índice {AUXILIAR_DESC_INDEX}: '{desc_col_final_source}'")
        else:
            print(f"Advertencia: No se pudo encontrar la columna de descripción ni por nombre '{desc_clean}' ni por índice {AUXILIAR_DESC_INDEX}.")
            # Se creará una columna vacía más adelante

        # Verificar que las columnas esenciales (fecha, doc, debito, credito) se encontraron y existen
        essential_cols_orig = [fecha_col_orig, doc_col_orig, debito_col_orig, credito_col_orig]
        missing_details = []
        if not fecha_col_orig or fecha_col_orig not in df_data.columns: missing_details.append(f"'{AUXILIAR_FECHA}'")
        if not doc_col_orig or doc_col_orig not in df_data.columns: missing_details.append(f"'{AUXILIAR_DOCUMENTO}'")
        if not debito_col_orig or debito_col_orig not in df_data.columns: missing_details.append(f"'{AUXILIAR_DEBITO}(s)'")
        if not credito_col_orig or credito_col_orig not in df_data.columns: missing_details.append(f"'{AUXILIAR_CREDITO}(s)'")

        if missing_details:
            raise KeyError(f"Faltan columnas esenciales después de identificar la cabecera: {', '.join(missing_details)}. Columnas encontradas en datos: {list(df_data.columns)}")

        # --- Procesamiento de Datos Seleccionados ---
        # Crear un DataFrame temporal solo con las columnas necesarias (usando nombres originales)
        cols_to_process = [fecha_col_orig, doc_col_orig, debito_col_orig, credito_col_orig]
        if desc_col_final_source: # Añadir solo si se encontró una fuente para descripción
            cols_to_process.append(desc_col_final_source)

        # Seleccionar solo las columnas a procesar, asegurándose que existen
        cols_to_process_existing = [col for col in cols_to_process if col in df_data.columns]
        df_process = df_data[cols_to_process_existing].copy()

        # 1. Formatear fecha
        df_process[FECHA_CONCILIACION] = df_process[fecha_col_orig].apply(format_date_robust)
        original_rows = len(df_process)
        parsed_dates_count = df_process[FECHA_CONCILIACION].notna().sum()
        print(f"Info SIESA: {parsed_dates_count} de {original_rows} fechas parseadas correctamente (col: '{fecha_col_orig}').")
        if parsed_dates_count < original_rows:
             # Opcional: investigar por qué algunas fechas no se parsearon
             # print("Fechas no parseadas:")
             # print(df_process[df_process[FECHA_CONCILIACION].isna()][fecha_col_orig])
             pass


        # 2. Eliminar filas sin fecha válida (CRUCIAL)
        rows_before_date_drop = len(df_process)
        df_process = df_process.dropna(subset=[FECHA_CONCILIACION])
        rows_after_date_drop = len(df_process)
        if rows_before_date_drop > rows_after_date_drop:
            print(f"Info: Se eliminaron {rows_before_date_drop - rows_after_date_drop} filas por no tener fecha válida.")

        if df_process.empty:
            print(f"Advertencia: No quedaron filas válidas en {file_path} después de procesar y requerir fechas válidas.")
            return None

        # 3. Formatear débito y crédito (convertir a número)
        # Aplicar format_currency que maneja texto, NaN, etc.
        df_process[debito_col_orig] = df_process[debito_col_orig].apply(format_currency)
        df_process[credito_col_orig] = df_process[credito_col_orig].apply(format_currency)

        # --- Construcción del DataFrame Final ---
        df_final = pd.DataFrame()
        df_final[FECHA_CONCILIACION] = df_process[FECHA_CONCILIACION]
        # Convertir documento a string por si acaso
        df_final['documento_auxiliar'] = df_process[doc_col_orig].astype(str)
        # Asignar descripción desde la fuente encontrada o poner NaN/None
        if desc_col_final_source:
            df_final['descripcion_auxiliar'] = df_process[desc_col_final_source].astype(str).fillna('') # Convertir a str, llenar NaN con ''
        else:
            df_final['descripcion_auxiliar'] = '' # Columna vacía si no se encontró fuente
        df_final[AUXILIAR_DEBITO] = df_process[debito_col_orig]
        df_final[AUXILIAR_CREDITO] = df_process[credito_col_orig]

        # Verificar que todas las columnas finales estándar estén presentes
        if not all(col in df_final.columns for col in AUXILIAR_COLUMNAS_FINALES):
            missing_final = [col for col in AUXILIAR_COLUMNAS_FINALES if col not in df_final.columns]
            raise KeyError(f"Error interno: Faltan las columnas finales estándar esperadas: {missing_final}. Columnas actuales: {list(df_final.columns)}")

        print(f"Info: Procesamiento SIESA completado. {len(df_final)} filas válidas.")
        print(f"Info: Columnas finales del auxiliar SIESA: {list(df_final.columns)}")
        # Asegurar el orden de las columnas finales
        return df_final[AUXILIAR_COLUMNAS_FINALES]

    except FileNotFoundError: print(f"Error: No se encontró el archivo {file_path}"); return None
    except ValueError as ve: print(f"Error de valor procesando {file_path}: {ve}"); return None
    except KeyError as ke: print(f"Error: Problema con la columna {ke} procesando {file_path}. Verifique nombres de columna y estructura."); return None
    except Exception as e:
        # Captura cualquier otra excepción no prevista
        import traceback
        print(f"Error inesperado al procesar el archivo auxiliar SIESA {file_path}:")
        traceback.print_exc() # Imprime el traceback completo para depuración
        return None


def transform_bancolombia_statement(file_path: str) -> Optional[pd.DataFrame]:
    """
    Lee y transforma un archivo de extracto bancario de Bancolombia (CSV - 9 cols).

    Args:
        file_path: Ruta al archivo CSV.

    Returns:
        Un DataFrame de pandas con ['fecha_norm', 'movimiento', 'descripcion_extracto']
        o None si ocurre un error.
    """
    try:
        # Intentar leer con detección automática de separador, pero preferir coma.
        # Usar dtype=str para evitar conversiones automáticas de números o fechas.
        # Especificar encoding puede ser necesario si hay caracteres especiales.
        try:
            df = pd.read_csv(file_path, sep=None, engine='python', header=None, dtype=str, encoding='utf-8')
            print(f"Info: Archivo {file_path} leído con separador detectado (o por defecto).")
            # Verificar si realmente se usó coma o si detectó otro separador
            # if df.shape[1] == 1: # Si solo hay una columna, probablemente falló la detección
            #     print("Advertencia: Parece que el separador no se detectó correctamente (solo 1 columna). Intentando con coma explícita.")
            #     df = pd.read_csv(file_path, sep=',', header=None, dtype=str, encoding='utf-8')

        except pd.errors.ParserError as pe:
             print(f"Error de parseo al leer CSV {file_path}: {pe}. Verifique el formato y separador.")
             return None
        except FileNotFoundError:
             print(f"Error: No se encontró el archivo {file_path}")
             return None
        except Exception as read_err:
            print(f"Error inesperado al LEER el archivo CSV {file_path}: {read_err}")
            return None


        num_cols_actual = df.shape[1]
        print(f"Info: Archivo {file_path} leído con {num_cols_actual} columnas.")

        # Validar estrictamente que tenga 9 columnas
        if num_cols_actual != 9:
            raise ValueError(f"El archivo {file_path} tiene {num_cols_actual} columnas, pero el formato esperado es de exactamente 9 columnas.")

        # Asignar nombres de columna esperados para el formato de 9 columnas
        column_names = EXTRACTO_COLUMNAS_CSV_9COLS_CORRECTO
        df.columns = column_names
        print(f"Info: Columnas asignadas para formato de 9: {list(df.columns)}")

        # Verificar si las columnas fuente requeridas existen después de asignar nombres
        missing_required_cols = [col for col in EXTRACTO_COLUMNAS_REQUERIDAS_FUENTE if col not in df.columns]
        if missing_required_cols:
            raise ValueError(f"El archivo {file_path} (después de asignar nombres) no contiene las columnas fuente requeridas: {missing_required_cols}. Nombres asignados: {column_names}")

        # --- Procesamiento de Datos ---
        # 1. Formatear fecha
        df[FECHA_CONCILIACION] = df['fecha_raw'].apply(format_date_robust)
        original_rows_ext = len(df)
        parsed_dates_count_ext = df[FECHA_CONCILIACION].notna().sum()
        print(f"Info Extracto: {parsed_dates_count_ext} de {original_rows_ext} fechas parseadas correctamente (col: 'fecha_raw').")

        # 2. Eliminar filas sin fecha válida
        rows_before_date_drop_ext = len(df)
        df = df.dropna(subset=[FECHA_CONCILIACION])
        rows_after_date_drop_ext = len(df)
        if rows_before_date_drop_ext > rows_after_date_drop_ext:
            print(f"Info: Se eliminaron {rows_before_date_drop_ext - rows_after_date_drop_ext} filas del extracto por no tener fecha válida.")


        if df.empty:
            print(f"Advertencia: No quedaron filas válidas en {file_path} después de procesar y requerir fechas válidas.")
            return None

        # 3. Formatear movimiento (moneda)
        df[MOVIMIENTO_CONCILIACION] = df['movimiento_raw'].apply(format_currency)

        # 4. Filtrar filas no deseadas por descripción (asegurándose que la columna existe)
        if 'descripcion_raw' in df.columns:
            # Convertir a string por si acaso y limpiar espacios
            df['descripcion_clean_temp'] = df['descripcion_raw'].astype(str).str.strip().str.upper()
            rows_before_desc_filter = len(df)
            df = df[~df['descripcion_clean_temp'].isin(EXTRACTO_VALORES_A_EXCLUIR_DESC)]
            rows_after_desc_filter = len(df)
            if rows_before_desc_filter > rows_after_desc_filter:
                 print(f"Info: Se eliminaron {rows_before_desc_filter - rows_after_desc_filter} filas por descripción excluida ({EXTRACTO_VALORES_A_EXCLUIR_DESC}).")
            df = df.drop(columns=['descripcion_clean_temp']) # Eliminar columna temporal
        else:
            # Esto no debería pasar si la validación inicial funcionó, pero por si acaso
            print("Advertencia: No se encontró la columna 'descripcion_raw' para filtrar por descripción.")

        if df.empty:
            print(f"Advertencia: No quedaron filas válidas en {file_path} después de filtrar por descripción.")
            return None

        # --- Construcción del DataFrame Final ---
        df_final = pd.DataFrame()
        df_final[FECHA_CONCILIACION] = df[FECHA_CONCILIACION]
        df_final[MOVIMIENTO_CONCILIACION] = df[MOVIMIENTO_CONCILIACION]
        # Tomar la descripción original (antes de limpiar para filtrar)
        df_final['descripcion_extracto'] = df['descripcion_raw'].astype(str).fillna('') if 'descripcion_raw' in df.columns else ''

        # Verificar que las columnas finales esperadas estén presentes
        missing_final_cols = [col for col in EXTRACTO_COLUMNAS_FINALES if col not in df_final.columns]
        if missing_final_cols:
            raise ValueError(f"Error interno: No se generaron las columnas finales esperadas para el extracto: {missing_final_cols}")

        print(f"Info: Procesamiento extracto Bancolombia completado. {len(df_final)} filas válidas.")
        print(f"Info: Columnas finales del extracto: {list(df_final.columns)}")
        return df_final[EXTRACTO_COLUMNAS_FINALES]

    # Manejo específico de errores esperados
    except FileNotFoundError: print(f"Error: No se encontró el archivo {file_path}"); return None
    except ValueError as ve: print(f"Error de valor procesando {file_path}: {ve}"); return None
    except KeyError as ke: print(f"Error: Falta la columna esperada {ke} durante el procesamiento de {file_path}. Verifique el formato del CSV y los nombres asignados."); return None
    # Captura genérica para errores no previstos
    except Exception as e:
        import traceback
        print(f"Error inesperado al procesar el extracto Bancolombia {file_path}:")
        traceback.print_exc()
        return None


# --- Función transform_bancolombia_movements (si la necesitas) ---
# Asegúrate de que las constantes MOVIMIENTO_* estén definidas globalmente si usas esta función
def transform_bancolombia_movements(file_path: str) -> Optional[pd.DataFrame]:
    """Lee y transforma un archivo de movimientos bancarios de Bancolombia (CSV)."""
    try:
        df = pd.read_csv(file_path, sep=',', decimal='.', header=None, dtype=str)
        if df.shape[1] <= max(MOVIMIENTO_COLUMNAS_FIJAS_INDICES):
            raise ValueError(f"El archivo {file_path} no tiene suficientes columnas para extraer los índices {MOVIMIENTO_COLUMNAS_FIJAS_INDICES}.")

        # Seleccionar columnas por índice y asignar nombres
        df = df.iloc[:, MOVIMIENTO_COLUMNAS_FIJAS_INDICES]
        df.columns = MOVIMIENTO_COLUMNAS_NOMBRES

        # Procesar fecha y movimiento
        df[FECHA_CONCILIACION] = df[MOVIMIENTO_FECHA].apply(format_date_robust)
        df = df.dropna(subset=[FECHA_CONCILIACION]) # Eliminar filas sin fecha válida

        if df.empty:
            print(f"Advertencia: No quedaron filas válidas en {file_path} (movimientos) después de procesar fechas.")
            return None

        df[MOVIMIENTO_CONCILIACION] = df[MOVIMIENTO_VALOR].apply(format_currency)

        # Crear DataFrame final con nombres estándar
        df_final = df[[FECHA_CONCILIACION, MOVIMIENTO_CONCILIACION, MOVIMIENTO_DESC, MOVIMIENTO_CUENTA]].copy()
        df_final.rename(columns={
            MOVIMIENTO_DESC: 'descripcion_extracto', # Usar el mismo nombre que el otro formato de extracto
            MOVIMIENTO_CUENTA: 'cuenta_extracto'     # Nombre específico para esta columna si existe
        }, inplace=True)

        # Devolver las columnas relevantes en un orden consistente
        # Ajusta las columnas devueltas si necesitas 'cuenta_extracto'
        final_cols = [FECHA_CONCILIACION, MOVIMIENTO_CONCILIACION, 'descripcion_extracto']
        if 'cuenta_extracto' in df_final.columns:
             final_cols.append('cuenta_extracto')

        return df_final[final_cols]

    except FileNotFoundError: print(f"Error: No se encontró el archivo {file_path}"); return None
    except ValueError as ve: print(f"Error de valor procesando {file_path}: {ve}"); return None
    except IndexError: print(f"Error: No se pudieron seleccionar las columnas por índice en {file_path}. ¿El formato es correcto?"); return None
    except Exception as e:
        import traceback
        print(f"Error inesperado al procesar movimientos Bancolombia {file_path}:")
        traceback.print_exc()
        return None

# --- Función de Conciliación ---
def reconcile_data(
    df_ledger: pd.DataFrame,
    df_statement: pd.DataFrame,
    include_ids: bool = True # Nuevo parámetro para incluir IDs si están presentes
) -> Optional[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """
    Realiza una conciliación básica entre un libro auxiliar y un extracto bancario.
    Intenta hacer merge por movimiento y un contador para manejar duplicados.

    Args:
        df_ledger: DataFrame del libro auxiliar (SIESA procesado).
                   Debe tener ['fecha_norm', 'debito', 'credito', 'descripcion_auxiliar', 'documento_auxiliar'].
                   Si include_ids=True, también debe tener 'tx_id_ref'.
        df_statement: DataFrame del extracto bancario (Bancolombia procesado).
                      Debe tener ['fecha_norm', 'movimiento', 'descripcion_extracto'].
                      Si include_ids=True, también debe tener 'tx_id_ref'.
        include_ids: Si es True, espera 'tx_id_ref' en ambos DataFrames y los incluye
                     en el resultado para referencia.

    Returns:
        Tupla con (df_merged_all, df_successful, df_pending) o None si hay error.
        - df_merged_all: Resultado completo del merge outer.
        - df_successful: Filas que coincidieron en ambos lados.
        - df_pending: Filas que solo existen en un lado (left_only o right_only).
    """
    try:
        print("\n--- Iniciando reconcile_data ---")
        # --- Validación y Preparación Libro Auxiliar (Ledger) ---
        print("Preparando Libro Auxiliar (Ledger)...")
        if df_ledger is None or df_ledger.empty:
            print("Advertencia: DataFrame del libro auxiliar está vacío o es None. No se puede conciliar.")
            # Devolver DataFrames vacíos con estructura esperada para evitar errores posteriores
            empty_cols_success = ['movimiento', 'fecha_libro', 'documento_auxiliar', 'descripcion_auxiliar', 'debito', 'credito', 'fecha_extracto', 'descripcion_extracto']
            empty_cols_pending = empty_cols_success + ['_merge']
            if include_ids:
                empty_cols_success = ['tx_id_ref_x', 'tx_id_ref_y'] + empty_cols_success
                empty_cols_pending = ['tx_id_ref_x', 'tx_id_ref_y'] + empty_cols_pending
            return pd.DataFrame(columns=empty_cols_pending), pd.DataFrame(columns=empty_cols_success), pd.DataFrame(columns=empty_cols_pending)


        df_ledger_copy = df_ledger.copy()
        required_ledger_cols = [FECHA_CONCILIACION, AUXILIAR_DEBITO, AUXILIAR_CREDITO, 'descripcion_auxiliar', 'documento_auxiliar']
        if include_ids: required_ledger_cols.append('tx_id_ref')

        missing_ledger_cols = [col for col in required_ledger_cols if col not in df_ledger_copy.columns]
        if missing_ledger_cols:
            raise ValueError(f"El DataFrame del libro auxiliar no tiene las columnas esperadas: {missing_ledger_cols}. Columnas presentes: {list(df_ledger_copy.columns)}")

        # Calcular movimiento neto y contador para merge
        df_ledger_copy[MOVIMIENTO_CONCILIACION] = df_ledger_copy[AUXILIAR_DEBITO] - df_ledger_copy[AUXILIAR_CREDITO]
        # Asegurar que el movimiento sea float
        df_ledger_copy[MOVIMIENTO_CONCILIACION] = df_ledger_copy[MOVIMIENTO_CONCILIACION].astype(float)
        # Ordenar antes de cumcount para consistencia (opcional pero recomendado)
        df_ledger_copy = df_ledger_copy.sort_values(by=[MOVIMIENTO_CONCILIACION, FECHA_CONCILIACION])
        df_ledger_copy[CONTADOR_CONCILIACION] = df_ledger_copy.groupby(MOVIMIENTO_CONCILIACION).cumcount()

        # Seleccionar y renombrar columnas para el merge
        ledger_cols_for_merge = [
            MOVIMIENTO_CONCILIACION, CONTADOR_CONCILIACION, FECHA_CONCILIACION,
            'documento_auxiliar', 'descripcion_auxiliar', AUXILIAR_DEBITO, AUXILIAR_CREDITO
        ]
        if include_ids: ledger_cols_for_merge.append('tx_id_ref')

        # Verificar que todas las columnas seleccionadas existan realmente
        missing_ledger_merge_cols = [col for col in ledger_cols_for_merge if col not in df_ledger_copy.columns]
        if missing_ledger_merge_cols:
             raise ValueError(f"Error interno: Faltan columnas en df_ledger_copy antes del merge: {missing_ledger_merge_cols}")

        df_ledger_merge = df_ledger_copy[ledger_cols_for_merge].copy()
        df_ledger_merge.rename(columns={FECHA_CONCILIACION: 'fecha_libro'}, inplace=True)
        print(f"Ledger listo para merge. Columnas: {list(df_ledger_merge.columns)}")

        # --- Validación y Preparación Extracto Bancario (Statement) ---
        print("Preparando Extracto Bancario (Statement)...")
        if df_statement is None or df_statement.empty:
             print("Advertencia: DataFrame del extracto bancario está vacío o es None. No se puede conciliar.")
             # Devolver DataFrames vacíos
             empty_cols_success = ['movimiento', 'fecha_libro', 'documento_auxiliar', 'descripcion_auxiliar', 'debito', 'credito', 'fecha_extracto', 'descripcion_extracto']
             empty_cols_pending = empty_cols_success + ['_merge']
             if include_ids:
                 empty_cols_success = ['tx_id_ref_x', 'tx_id_ref_y'] + empty_cols_success
                 empty_cols_pending = ['tx_id_ref_x', 'tx_id_ref_y'] + empty_cols_pending
             return pd.DataFrame(columns=empty_cols_pending), pd.DataFrame(columns=empty_cols_success), pd.DataFrame(columns=empty_cols_pending)


        df_statement_copy = df_statement.copy()
        required_statement_cols = [FECHA_CONCILIACION, MOVIMIENTO_CONCILIACION, 'descripcion_extracto']
        if include_ids: required_statement_cols.append('tx_id_ref')

        missing_statement_cols = [col for col in required_statement_cols if col not in df_statement_copy.columns]
        if missing_statement_cols:
            raise ValueError(f"El DataFrame del extracto bancario no tiene las columnas esperadas: {missing_statement_cols}. Columnas presentes: {list(df_statement_copy.columns)}")

        # Asegurar que el movimiento sea float
        df_statement_copy[MOVIMIENTO_CONCILIACION] = df_statement_copy[MOVIMIENTO_CONCILIACION].astype(float)
        # Ordenar antes de cumcount
        df_statement_copy = df_statement_copy.sort_values(by=[MOVIMIENTO_CONCILIACION, FECHA_CONCILIACION])
        df_statement_copy[CONTADOR_CONCILIACION] = df_statement_copy.groupby(MOVIMIENTO_CONCILIACION).cumcount()

        # Seleccionar y renombrar columnas para el merge
        statement_cols_for_merge = [
            MOVIMIENTO_CONCILIACION, CONTADOR_CONCILIACION, FECHA_CONCILIACION,
            'descripcion_extracto'
        ]
        if include_ids: statement_cols_for_merge.append('tx_id_ref')

        missing_statement_merge_cols = [col for col in statement_cols_for_merge if col not in df_statement_copy.columns]
        if missing_statement_merge_cols:
             raise ValueError(f"Error interno: Faltan columnas en df_statement_copy antes del merge: {missing_statement_merge_cols}")

        df_statement_merge = df_statement_copy[statement_cols_for_merge].copy()
        df_statement_merge.rename(columns={FECHA_CONCILIACION: 'fecha_extracto'}, inplace=True)
        print(f"Statement listo para merge. Columnas: {list(df_statement_merge.columns)}")

        # --- Conciliación (Merge) ---
        print(f"\nRealizando merge 'outer' en [{MOVIMIENTO_CONCILIACION}, {CONTADOR_CONCILIACION}]...")
        # Claves para el merge
        merge_keys = [MOVIMIENTO_CONCILIACION, CONTADOR_CONCILIACION]

        # Realizar el merge
        reconciled_data = pd.merge(
            df_ledger_merge, df_statement_merge,
            on=merge_keys,
            how='outer', # outer: mantener todas las filas de ambos lados
            indicator=True, # Añade columna '_merge' (left_only, right_only, both)
            suffixes=('_libro', '_extracto') # Sufijos por si hay columnas con mismo nombre (aparte de las claves)
        )
        print(f"Merge completado. Dimensiones del resultado: {reconciled_data.shape}")
        print(f"Columnas después del Merge: {list(reconciled_data.columns)}")
        # Contar resultados del merge
        print("Distribución del resultado del merge:")
        print(reconciled_data['_merge'].value_counts())

        # --- Separación de Resultados ---
        # Conciliados exitosamente (presentes en ambos lados)
        successful_reconciliation = reconciled_data[reconciled_data['_merge'] == 'both'].copy()
        # Pendientes (presentes solo en un lado)
        pending_reconciliation = reconciled_data[reconciled_data['_merge'] != 'both'].copy()

        # Limpiar columnas innecesarias de los resultados finales
        cols_to_drop_success = [CONTADOR_CONCILIACION, '_merge']
        # Eliminar solo si existen
        successful_reconciliation.drop(columns=[col for col in cols_to_drop_success if col in successful_reconciliation.columns], inplace=True)

        cols_to_drop_pending = [CONTADOR_CONCILIACION] # Mantener '_merge' en pendientes
        pending_reconciliation.drop(columns=[col for col in cols_to_drop_pending if col in pending_reconciliation.columns], inplace=True)

        # Renombrar columnas de ID si se usaron (Pandas añade sufijos _x, _y en merge si la columna existe en ambos)
        if include_ids:
            if 'tx_id_ref_libro' in successful_reconciliation.columns: successful_reconciliation.rename(columns={'tx_id_ref_libro': 'tx_id_ref_x'}, inplace=True)
            if 'tx_id_ref_extracto' in successful_reconciliation.columns: successful_reconciliation.rename(columns={'tx_id_ref_extracto': 'tx_id_ref_y'}, inplace=True)
            if 'tx_id_ref_libro' in pending_reconciliation.columns: pending_reconciliation.rename(columns={'tx_id_ref_libro': 'tx_id_ref_x'}, inplace=True)
            if 'tx_id_ref_extracto' in pending_reconciliation.columns: pending_reconciliation.rename(columns={'tx_id_ref_extracto': 'tx_id_ref_y'}, inplace=True)


        print(f"--- Conciliación finalizada ---")
        print(f"Registros Conciliados: {len(successful_reconciliation)}")
        print(f"Registros Pendientes (Libro): {len(pending_reconciliation[pending_reconciliation['_merge'] == 'left_only'])}")
        print(f"Registros Pendientes (Extracto): {len(pending_reconciliation[pending_reconciliation['_merge'] == 'right_only'])}")

        # Devolver el merge completo, los conciliados y los pendientes
        return reconciled_data, successful_reconciliation, pending_reconciliation

    except KeyError as ke:
        print(f"Error de conciliación: Falta la columna requerida '{ke}'. Verifique los DataFrames de entrada.")
        import traceback
        traceback.print_exc()
        return None
    except ValueError as ve:
        print(f"Error de valor durante la conciliación: {ve}")
        import traceback
        traceback.print_exc()
        return None
    except Exception as e:
        print(f"Error inesperado durante la conciliación:")
        import traceback
        traceback.print_exc()
        return None
    


# --- Ejemplo de Uso (Descomentar y adaptar rutas de archivo para probar directamente) ---
# Este bloque solo se ejecuta si corres `python processing.py` directamente.
# No se ejecutará cuando FastAPI importe las funciones.
if __name__ == "__main__":
    print("--- Ejecutando processing.py directamente para prueba ---")
    # Rutas a los archivos (¡reemplazar con las rutas reales de tus archivos de prueba!)
    # Asegúrate de que estos archivos existan si descomentas y ejecutas
    ruta_auxiliar_siesa = r"G:\Mi unidad\automatizaciones\12_conciliacion_bancaria\siesa_bancolombia_abril_2025.xlsx" # Usando tu nombre de archivo
    ruta_extracto_bancolombia = r"G:\Mi unidad\automatizaciones\12_conciliacion_bancaria\CSV_27799726048_000000901195703_20250502_08133217.csv" # Usando tu nombre de archivo
    # ruta_movimientos_bancolombia = 'ruta/a/tu/movimientos.csv' # Si usas este en lugar del extracto

    print("\nProcesando archivo auxiliar SIESA...")
    df_libro = transform_siesa_auxiliary(ruta_auxiliar_siesa)

    print("\nProcesando extracto Bancolombia...")
    df_extracto = transform_bancolombia_statement(ruta_extracto_bancolombia)
    # O si usas el archivo de movimientos:
    # df_extracto = transform_bancolombia_movements(ruta_movimientos_bancolombia)

    if df_libro is not None and not df_libro.empty:
        print(f"\nLibro Auxiliar (SIESA) procesado exitosamente. {len(df_libro)} filas.")
        # print("Primeras filas SIESA:")
        # print(df_libro.head())
    else:
         print("\nFallo al procesar Libro Auxiliar (SIESA) o resultó vacío.")


    if df_extracto is not None and not df_extracto.empty:
        print(f"\nExtracto Bancolombia procesado exitosamente. {len(df_extracto)} filas.")
        # print("Primeras filas Extracto:")
        # print(df_extracto.head())
    else:
         print("\nFallo al procesar Extracto Bancolombia o resultó vacío.")


    # Solo intentar conciliar si ambos DataFrames se procesaron y no están vacíos
    if df_libro is not None and not df_libro.empty and df_extracto is not None and not df_extracto.empty:
        print("\nRealizando conciliación...")
        # Llamar a reconcile_data sin IDs ya que no los generamos en esta prueba directa
        resultado_conciliacion = reconcile_data(df_libro, df_extracto, include_ids=False)

        if resultado_conciliacion:
            todos, conciliados, pendientes = resultado_conciliacion

            print(f"\n--- Resumen de Conciliación (Prueba Directa) ---")
            print(f"Total registros después del merge: {len(todos)}")
            print(f"Registros Conciliados Exitosamente: {len(conciliados)}")
            print(f"Registros Pendientes (Libro): {len(pendientes[pendientes['_merge'] == 'left_only'])}")
            print(f"Registros Pendientes (Extracto): {len(pendientes[pendientes['_merge'] == 'right_only'])}")

            # Opcional: Guardar resultados en archivos Excel para revisar
            try:
                # Definir el orden deseado de columnas para el Excel de pendientes
                orden_columnas_pendientes = [
                    'movimiento', 'fecha_libro', 'documento_auxiliar', 'descripcion_auxiliar', 'debito', 'credito',
                    'fecha_extracto', 'descripcion_extracto', '_merge'
                ]
                # Usar solo columnas que existan en el DataFrame pendientes
                columnas_existentes_pendientes = [col for col in orden_columnas_pendientes if col in pendientes.columns]
                pendientes_excel = pendientes[columnas_existentes_pendientes]

                # Definir el orden deseado de columnas para el Excel de conciliados
                orden_columnas_conciliados = [
                    'movimiento', 'fecha_libro', 'documento_auxiliar', 'descripcion_auxiliar', 'debito', 'credito',
                    'fecha_extracto', 'descripcion_extracto'
                ]
                 # Usar solo columnas que existan en el DataFrame conciliados
                columnas_existentes_conciliados = [col for col in orden_columnas_conciliados if col in conciliados.columns]
                conciliados_excel = conciliados[columnas_existentes_conciliados]

                # Usar ExcelWriter para guardar en diferentes hojas
                output_filename = 'resultado_conciliacion_prueba.xlsx'
                with pd.ExcelWriter(output_filename) as writer:
                    conciliados_excel.to_excel(writer, sheet_name='Conciliados', index=False)
                    pendientes_excel.to_excel(writer, sheet_name='Pendientes', index=False)
                    # Opcional: guardar el merge completo
                    # todos.to_excel(writer, sheet_name='Merge_Completo', index=False)
                print(f"\nResultados de la prueba guardados en '{output_filename}'")
            except Exception as e:
                print(f"\nError al guardar los resultados de la prueba en Excel: {e}")