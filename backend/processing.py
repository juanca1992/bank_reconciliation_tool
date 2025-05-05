# backend/processing.py

import pandas as pd
import numpy as np
from datetime import datetime
import traceback
from typing import Optional, Tuple, List, Dict, Any, Callable, Literal
import io

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


# --- Constantes y Nombres Estándar ---
# Nombres estándar internos que usará la aplicación
FECHA_CONCILIACION = 'fecha_norm'
MOVIMIENTO_CONCILIACION = 'movimiento' # Para extractos bancarios (positivo/negativo)
AUXILIAR_DEBITO = 'debito' # Para contabilidad
AUXILIAR_CREDITO = 'credito' # Para contabilidad
DESCRIPCION_EXTRACTO = 'descripcion_extracto'
DESCRIPCION_AUXILIAR = 'descripcion_auxiliar'
DOCUMENTO_AUXILIAR = 'documento_auxiliar'
ID_TRANSACCION_ORIGINAL = 'tx_id_original' # Para referencia, si existe
CONTADOR_CONCILIACION = 'contador' # Para lógica de conciliación interna

# Columnas requeridas mínimas para cada tipo después del procesamiento
MIN_COLS_BANK = [FECHA_CONCILIACION, MOVIMIENTO_CONCILIACION, DESCRIPCION_EXTRACTO]
MIN_COLS_ACCOUNTING = [FECHA_CONCILIACION, AUXILIAR_DEBITO, AUXILIAR_CREDITO, DESCRIPCION_AUXILIAR, DOCUMENTO_AUXILIAR]


# --- Funciones de Formateo (Helpers) ---

def clean_text(text: Any) -> str:
    """Limpia texto: convierte a minúsculas, quita acentos y espacios."""
    if pd.isna(text): return ''
    if not isinstance(text, str): text = str(text)
    cleaned = unidecode(text).lower().strip()
    return cleaned

def format_currency(value: Any) -> float:
    """Convierte un valor a float, manejando formato monetario (espera '.' decimal)."""
    if pd.isna(value): return 0.0
    try:
        if isinstance(value, (int, float)): return round(float(value), 2)
        if isinstance(value, str):
            cleaned_value = value.replace('$', '').strip()
            # Intentar quitar separador de miles (coma) y luego reemplazar coma decimal por punto si es necesario
            if ',' in cleaned_value and '.' in cleaned_value: # Formato tipo 1.234,56
                 cleaned_value = cleaned_value.replace('.', '').replace(',', '.')
            elif ',' in cleaned_value: # Puede ser 1,234 (miles) o 1,23 (decimal)
                # Heurística: si la última coma está seguida por 1 o 2 dígitos, es decimal
                last_comma_idx = cleaned_value.rfind(',')
                if last_comma_idx != -1 and len(cleaned_value) - last_comma_idx - 1 <= 2:
                     cleaned_value = cleaned_value.replace('.', '').replace(',', '.') # Tratar como decimal
                else:
                     cleaned_value = cleaned_value.replace(',', '') # Tratar como miles
            # Si no hay comas, o solo punto, asumir formato estándar o solo punto decimal
            return round(float(cleaned_value), 2)
        else: return round(float(value), 2)
    except (ValueError, TypeError) as e:
        print(f"WARN format_currency: Valor '{value}' no formateado a float: {e}")
        return 0.0

def format_date_robust(date_value: Any) -> Optional[datetime.date]:
    """Intenta convertir un valor a fecha (objeto date), probando varios formatos."""
    if pd.isna(date_value) or not date_value: return None
    if isinstance(date_value, datetime): return date_value.date()
    if isinstance(date_value, np.datetime64):
        try:
            ts = pd.Timestamp(date_value); return None if pd.isna(ts) else ts.to_pydatetime().date()
        except Exception: pass # Intentar otros métodos abajo
    date_str = str(date_value).strip()
    formats_to_try = [
        '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d', # Comunes con separadores
        '%Y%m%d', '%d%m%Y',                          # Sin separadores
        '%Y-%m-%dT%H:%M:%S', '%Y/%m/%d %H:%M:%S',      # Con hora (ignorar hora)
        '%d/%m/%y', '%d-%m-%y',                        # Año corto
        # Añadir formatos específicos si se identifican
    ]
    for fmt in formats_to_try:
        try: return datetime.strptime(date_str.split(' ')[0], fmt).date() # Intentar solo parte fecha
        except (ValueError, TypeError): continue
    # Fallback con PANDAS si los formatos comunes fallan
    try:
        dt = pd.to_datetime(date_str, errors='coerce', dayfirst=True)
        if not pd.isna(dt): return dt.date()
    except Exception: pass
    print(f"WARN format_date_robust: No se pudo parsear la fecha '{date_value}'")
    return None

def find_header_row(df: pd.DataFrame, keywords: List[str], max_rows_scan: int = 20) -> int:
    """Encuentra el índice de la fila de cabecera buscando keywords."""
    keywords_clean = [clean_text(k) for k in keywords]
    print(f"DEBUG find_header_row: Buscando keywords {keywords_clean}")
    for i, row in df.head(max_rows_scan).iterrows():
        row_values_clean = {clean_text(v) for v in row.values if pd.notna(v)}
        print(f"DEBUG find_header_row: Fila {i} valores limpios: {row_values_clean}")
        if all(kw in row_values_clean for kw in keywords_clean):
            print(f"DEBUG find_header_row: Cabecera encontrada en índice {i}")
            return i
    print(f"WARN find_header_row: No se encontró cabecera con keywords {keywords_clean}")
    return -1 # No encontrado


# --- Configuración de Formatos ---
# Define aquí las configuraciones para cada formato de archivo soportado.
# La clave es un identificador único (ej: 'bancolombia_csv_9col', 'siesa_xlsx')
FILE_FORMAT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "bancolombia_csv_9col": {
        "type": "bank",
        "read_function": pd.read_csv,
        "read_options": {"sep": None, "engine": 'python', "header": None, "dtype": str, "encoding": 'utf-8'},
        "expected_columns": 9,
        "column_names_initial": [
            'cuenta_raw', 'codigo_trans_raw', 'col_3_ignorar', 'fecha_raw',
            'col_5_ignorar', 'movimiento_raw', 'codigo_desc_raw', 'descripcion_raw', 'col_9_ignorar'
        ],
        "mapping": {
            FECHA_CONCILIACION: ('fecha_raw', format_date_robust),
            MOVIMIENTO_CONCILIACION: ('movimiento_raw', format_currency),
            DESCRIPCION_EXTRACTO: ('descripcion_raw', clean_text),
        },
        "filter_rows": {
            "column": "descripcion_raw", # Columna original antes del mapeo
            "exclude_values": ['SALDO DIA', 'SALDO FINAL', 'SALDO INICIAL'],
            "clean_first": True # Limpiar valor de la columna antes de comparar
        },
        "final_columns": MIN_COLS_BANK,
    },
    "siesa_xlsx": {
        "type": "accounting",
        "read_function": pd.read_excel, # Usar función wrapper para manejar múltiples hojas
        "read_options": {"header": None, "sheet_name": None, "dtype": str},
        "header_detection": {
            "keywords": ['Fecha', 'Documento', 'Debitos', 'Creditos'], # Keywords para encontrar la fila cabecera
            # Alternativa: "row_index": 5 # Si la cabecera siempre está en la misma fila (0-based)
        },
        "mapping": {
            # Mapea Nombre Interno a (Nombre Columna Archivo, Función Formateo)
            # La función de formateo es opcional, si no se pone, se usa el valor tal cual
            FECHA_CONCILIACION: ('Fecha', format_date_robust),
            DOCUMENTO_AUXILIAR: ('Documento', str),
            # Para débito/crédito, podemos necesitar lógica extra si los nombres varían
            AUXILIAR_DEBITO: (['Debitos', 'Debito', 'Débito', 'Débitos'], format_currency), # Lista de posibles nombres
            AUXILIAR_CREDITO: (['Creditos', 'Credito', 'Crédito', 'Créditos'], format_currency),
            # Descripcion puede venir de varias columnas, intentaremos concatenar si existen
            DESCRIPCION_AUXILIAR: (['Descripcion Transaccion', 'Descripcion', 'Descripción', 'Detalle'], str), # Intentará usar la primera que encuentre
            # ID_TRANSACCION_ORIGINAL: ('Id Interno', str) # Ejemplo si hubiera un ID único
        },
        "combine_description": { # Opcional: Concatena estas columnas si existen para formar la descripción final
             "source_columns": ['C.O.', 'U.N.', 'Descripcion Transaccion', 'Descripcion', 'Descripción', 'Detalle', 'text1', 'text2', 'text3'], # Intentará encontrar estas
             "target_column": DESCRIPCION_AUXILIAR,
             "separator": " | "
        },
        "final_columns": MIN_COLS_ACCOUNTING,
        # "filter_rows": {...} # Se podría añadir filtro si fuera necesario
    },
    # --- Añadir más configuraciones aquí ---
    # Ejemplo ficticio para otro banco:
    # "otro_banco_csv": {
    #     "type": "bank",
    #     "read_function": pd.read_csv,
    #     "read_options": {"sep": ";", "header": 0, "encoding": 'latin-1'}, # Cabecera en fila 0
    #     "mapping": {
    #         FECHA_CONCILIACION: ('Transaction Date', lambda d: format_date_robust(d, format='%m/%d/%Y')), # Formato específico
    #         MOVIMIENTO_CONCILIACION: ('Amount', format_currency),
    #         DESCRIPCION_EXTRACTO: ('Details', clean_text),
    #     },
    #     "final_columns": MIN_COLS_BANK,
    # }
}

# --- Función Genérica de Procesamiento ---

def read_excel_flexible(io: Any, **kwargs) -> Optional[pd.DataFrame]:
    """Lee un archivo Excel, intentando manejar múltiples hojas."""
    try:
        excel_content = pd.read_excel(io, **kwargs)
        if isinstance(excel_content, pd.DataFrame):
            print("DEBUG read_excel_flexible: Leída una sola hoja.")
            return excel_content
        elif isinstance(excel_content, dict):
            if not excel_content:
                print("WARN read_excel_flexible: Archivo Excel vacío (sin hojas).")
                return None
            # Intentar encontrar una hoja con datos o usar la primera
            non_empty_sheets = {name: df for name, df in excel_content.items() if not df.empty}
            if not non_empty_sheets:
                 print("WARN read_excel_flexible: Archivo Excel con hojas, pero todas vacías.")
                 return None
            # Priorizar hojas con nombres comunes o usar la primera no vacía
            common_sheet_names = ['Sheet1', 'Hoja1', 'Movimientos', 'Auxiliar', 'Datos']
            for name in common_sheet_names:
                if name in non_empty_sheets:
                    print(f"DEBUG read_excel_flexible: Usando hoja '{name}'.")
                    return non_empty_sheets[name]
            first_sheet_name = list(non_empty_sheets.keys())[0]
            print(f"DEBUG read_excel_flexible: No se encontraron hojas comunes, usando la primera hoja no vacía: '{first_sheet_name}'.")
            return non_empty_sheets[first_sheet_name]
        else:
            print(f"ERROR read_excel_flexible: Formato inesperado devuelto por pd.read_excel: {type(excel_content)}")
            return None
    except Exception as e:
        print(f"ERROR read_excel_flexible: Fallo al leer Excel: {e}")
        traceback.print_exc()
        return None

def process_uploaded_file(file_content: bytes, format_id: str) -> Optional[pd.DataFrame]:
    """
    Procesa el contenido de un archivo subido usando la configuración especificada.

    Args:
        file_content: El contenido binario del archivo.
        format_id: El identificador de la configuración a usar (ej: 'bancolombia_csv_9col').

    Returns:
        Un DataFrame de Pandas con las columnas estándar y datos procesados,
        o None si ocurre un error o el formato no es válido.
    """
    print(f"\n--- Iniciando process_uploaded_file para formato: {format_id} ---")
    if format_id not in FILE_FORMAT_CONFIGS:
        print(f"ERROR: Formato '{format_id}' no configurado en processing.py.")
        return None

    config = FILE_FORMAT_CONFIGS[format_id]
    file_type = config.get("type", "unknown") # bank o accounting

    try:
        # 1. Leer el archivo en un DataFrame
        read_func = config.get("read_function", pd.read_csv) # Default a CSV
        read_opts = config.get("read_options", {})
        file_stream = io.BytesIO(file_content)

        # Adaptar la lectura para Excel usando la función flexible
        if read_func == pd.read_excel:
            df_raw = read_excel_flexible(file_stream, **read_opts)
        else:
            try:
                df_raw = read_func(file_stream, **read_opts)
            except Exception as read_err:
                 # Intentar con otra codificación común si falla UTF-8
                if 'encoding' not in read_opts or read_opts.get('encoding', '').lower() == 'utf-8':
                    print("WARN: Falló lectura con UTF-8, intentando con latin-1...")
                    try:
                        file_stream.seek(0) # Reset stream
                        read_opts['encoding'] = 'latin-1'
                        df_raw = read_func(file_stream, **read_opts)
                    except Exception as read_err_latin1:
                        print(f"ERROR: Falló lectura con UTF-8 y latin-1: {read_err_latin1}")
                        raise ValueError(f"Error leyendo archivo: {read_err_latin1}") from read_err_latin1
                else:
                     print(f"ERROR: Falló lectura con codificación {read_opts.get('encoding')}: {read_err}")
                     raise ValueError(f"Error leyendo archivo: {read_err}") from read_err


        if df_raw is None or df_raw.empty:
            print(f"WARN: Archivo '{format_id}' leído pero resultó vacío o con error de lectura.")
            return pd.DataFrame(columns=config.get("final_columns", [])) # Devolver DF vacío con columnas esperadas

        print(f"DEBUG: Archivo leído. {len(df_raw)} filas iniciales.")
        df_raw.replace(r'^\s*$', pd.NA, regex=True, inplace=True) # Reemplazar vacíos por NA
        df_raw = df_raw.dropna(how='all').reset_index(drop=True) # Eliminar filas totalmente vacías
        if df_raw.empty:
             print(f"WARN: Archivo '{format_id}' vacío después de quitar filas vacías.")
             return pd.DataFrame(columns=config.get("final_columns", []))

        # 2. Validar número de columnas (si aplica)
        expected_cols = config.get("expected_columns")
        if expected_cols and df_raw.shape[1] != expected_cols:
            raise ValueError(f"Formato '{format_id}' esperaba {expected_cols} columnas, pero encontró {df_raw.shape[1]}.")

        # 3. Asignar/Detectar cabeceras
        header_row_idx = -1
        if "header_detection" in config:
            detection_cfg = config["header_detection"]
            if "row_index" in detection_cfg:
                header_row_idx = detection_cfg["row_index"]
                print(f"DEBUG: Usando índice de cabecera fijo: {header_row_idx}")
            elif "keywords" in detection_cfg:
                header_row_idx = find_header_row(df_raw, detection_cfg["keywords"])
        elif config.get("read_options", {}).get("header") == 0: # Si se leyó con header=0
             header_row_idx = -2 # Indica que ya se usó la fila 0 como cabecera
             print("DEBUG: Cabecera ya asignada en la lectura (header=0).")
        elif config.get("column_names_initial"):
             df_raw.columns = config["column_names_initial"]
             print(f"DEBUG: Nombres de columna iniciales asignados: {list(df_raw.columns)}")
             # Si no se detecta cabecera y hay nombres iniciales, asumimos que los datos empiezan en la fila 0
             df_data = df_raw
        else:
            print("WARN: No hay configuración de cabecera ni nombres iniciales definidos. Asumiendo fila 0 como datos.")
            df_data = df_raw # Asumir que los datos empiezan desde la fila 0

        if header_row_idx == -1 and 'df_data' not in locals(): # Si no se encontró header Y no se asignaron nombres iniciales
             raise ValueError(f"No se pudo encontrar o definir la cabecera para '{format_id}'.")
        elif header_row_idx >= 0: # Si se encontró índice de cabecera
            detected_columns = [str(v).strip() if pd.notna(v) else f'unnamed_{j}' for j, v in enumerate(df_raw.iloc[header_row_idx])]
            df_raw.columns = detected_columns
            df_data = df_raw.iloc[header_row_idx + 1:].reset_index(drop=True)
            print(f"DEBUG: Cabecera detectada en fila {header_row_idx}. Columnas: {detected_columns}")
        elif header_row_idx == -2: # Cabecera ya estaba en read_options
             df_data = df_raw
             print(f"DEBUG: Usando datos desde fila 0, columnas ya asignadas: {list(df_data.columns)}")

        # 4. Filtrar filas no deseadas (antes del mapeo si usa columnas originales)
        if "filter_rows" in config:
            filter_cfg = config["filter_rows"]
            col_to_filter = filter_cfg["column"]
            if col_to_filter in df_data.columns:
                exclude_vals = filter_cfg.get("exclude_values", [])
                clean_first = filter_cfg.get("clean_first", False)

                if exclude_vals:
                    vals_to_exclude_clean = {clean_text(v) for v in exclude_vals} if clean_first else set(exclude_vals)
                    filter_series = df_data[col_to_filter].apply(lambda x: clean_text(x) if clean_first else x)
                    rows_before = len(df_data)
                    df_data = df_data[~filter_series.isin(vals_to_exclude_clean)]
                    rows_dropped = rows_before - len(df_data)
                    if rows_dropped > 0: print(f"INFO: Filtradas {rows_dropped} filas basadas en '{col_to_filter}'.")
            else:
                print(f"WARN: Columna de filtro '{col_to_filter}' no encontrada en los datos.")

        if df_data.empty:
            print(f"WARN: No quedan datos válidos en '{format_id}' después de filtros iniciales.")
            return pd.DataFrame(columns=config.get("final_columns", []))

        # 5. Mapear y Formatear Columnas
        df_processed = pd.DataFrame()
        mapping = config.get("mapping", {})
        column_map_clean_to_original = {clean_text(col): col for col in df_data.columns if isinstance(col, str)}

        for target_col, source_info in mapping.items():
            source_col_names, format_func = None, None
            if isinstance(source_info, tuple):
                source_col_input, format_func = source_info
            else: # Solo nombre de columna
                source_col_input = source_info

            # Normalizar source_col_input a lista
            if isinstance(source_col_input, str):
                source_col_names = [source_col_input]
            elif isinstance(source_col_input, list):
                source_col_names = source_col_input
            else:
                 print(f"WARN: Configuración de mapeo inválida para '{target_col}'. Se ignora.")
                 continue

            # Encontrar la primera columna fuente que exista en el DataFrame
            actual_source_col = None
            for src_name in source_col_names:
                # Buscar por nombre exacto o por nombre limpio
                if src_name in df_data.columns:
                    actual_source_col = src_name
                    break
                src_name_clean = clean_text(src_name)
                if src_name_clean in column_map_clean_to_original:
                    actual_source_col = column_map_clean_to_original[src_name_clean]
                    break

            if actual_source_col:
                 print(f"DEBUG: Mapeando '{target_col}' desde '{actual_source_col}'...")
                 if format_func:
                     try:
                          df_processed[target_col] = df_data[actual_source_col].apply(format_func)
                     except Exception as fmt_err:
                          print(f"ERROR aplicando función de formato para '{target_col}' desde '{actual_source_col}': {fmt_err}")
                          traceback.print_exc()
                          # Considerar si continuar con datos crudos o fallar
                          df_processed[target_col] = df_data[actual_source_col] # Usar valor crudo como fallback
                 else:
                     df_processed[target_col] = df_data[actual_source_col]
            else:
                 print(f"WARN: No se encontró ninguna columna fuente {source_col_names} para mapear a '{target_col}'. Se usará valor por defecto (NaN o 0.0).")
                 # Crear columna con NaNs o 0.0 según el tipo esperado
                 if target_col in [MOVIMIENTO_CONCILIACION, AUXILIAR_DEBITO, AUXILIAR_CREDITO]:
                      df_processed[target_col] = 0.0
                 elif target_col == FECHA_CONCILIACION:
                      df_processed[target_col] = pd.NaT
                 else: # Descripción, Documento, etc.
                      df_processed[target_col] = '' # Usar string vacío

        # 6. Combinar Descripciones (Opcional)
        if "combine_description" in config:
            combine_cfg = config["combine_description"]
            source_cols = combine_cfg.get("source_columns", [])
            target_desc_col = combine_cfg.get("target_column", DESCRIPCION_AUXILIAR) # Default a auxiliar
            separator = combine_cfg.get("separator", " | ")

            cols_to_combine_found = []
            for src_name in source_cols:
                 if src_name in df_data.columns: cols_to_combine_found.append(src_name)
                 else:
                      src_name_clean = clean_text(src_name)
                      if src_name_clean in column_map_clean_to_original:
                           cols_to_combine_found.append(column_map_clean_to_original[src_name_clean])

            if cols_to_combine_found:
                print(f"DEBUG: Combinando columnas {cols_to_combine_found} en '{target_desc_col}'.")
                # Crear serie combinada, asegurando que sean strings y manejando NaNs
                combined_series = df_data[cols_to_combine_found].astype(str).apply(
                     lambda row: separator.join(row.dropna().astype(str)), axis=1
                )
                # Si la columna objetivo ya existe del mapeo, se sobrescribe. Si no, se crea.
                df_processed[target_desc_col] = combined_series.apply(clean_text)
            else:
                 print(f"WARN: No se encontraron columnas para combinar descripción para '{format_id}'.")
                 if target_desc_col not in df_processed: # Asegurar que la columna exista si no se pudo combinar
                     df_processed[target_desc_col] = ''

        # 7. Limpieza Final y Validación de Columnas
        # Eliminar filas donde la fecha es NaT (no se pudo parsear)
        initial_rows = len(df_processed)
        if FECHA_CONCILIACION in df_processed.columns:
             df_processed = df_processed.dropna(subset=[FECHA_CONCILIACION])
             dropped_rows = initial_rows - len(df_processed)
             if dropped_rows > 0: print(f"INFO: Eliminadas {dropped_rows} filas sin fecha válida.")

        # Asegurar tipos numéricos correctos y llenar NaNs con 0.0
        for col in [MOVIMIENTO_CONCILIACION, AUXILIAR_DEBITO, AUXILIAR_CREDITO]:
            if col in df_processed.columns:
                df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce').fillna(0.0)

        # Asegurar que las columnas de texto sean strings y llenar NaNs con ''
        for col in [DESCRIPCION_EXTRACTO, DESCRIPCION_AUXILIAR, DOCUMENTO_AUXILIAR]:
             if col in df_processed.columns:
                  df_processed[col] = df_processed[col].astype(str).fillna('')


        # Validar columnas finales requeridas para el tipo (bank/accounting)
        final_columns_expected = MIN_COLS_BANK if file_type == 'bank' else MIN_COLS_ACCOUNTING
        missing_cols = [col for col in final_columns_expected if col not in df_processed.columns]
        if missing_cols:
            raise ValueError(f"Error interno: Faltan columnas procesadas esenciales para '{format_id}' ({file_type}): {missing_cols}. Columnas presentes: {list(df_processed.columns)}")

        print(f"INFO: Procesamiento '{format_id}' completado. {len(df_processed)} filas válidas.")
        print(f"DEBUG: Columnas finales: {list(df_processed.columns)}")

        # Devolver solo las columnas finales esperadas (o todas las procesadas si no se especifican)
        output_cols = config.get("final_columns", list(df_processed.columns))
        # Asegurar que todas las columnas de output_cols existan en df_processed
        valid_output_cols = [col for col in output_cols if col in df_processed.columns]
        return df_processed[valid_output_cols]

    except FileNotFoundError:
        print(f"ERROR: Archivo no encontrado (esto no debería pasar con BytesIO).")
        return None
    except ValueError as ve:
        print(f"ERROR (ValueError) procesando '{format_id}': {ve}")
        traceback.print_exc()
        return None
    except KeyError as ke:
        print(f"ERROR (KeyError) procesando '{format_id}': Columna {ke}. Verifique configuración y archivo.")
        traceback.print_exc()
        return None
    except Exception as e:
        print(f"ERROR inesperado procesando '{format_id}': {e}")
        traceback.print_exc()
        return None


# --- Función de Conciliación Automática (Sin cambios importantes, pero asegurar nombres de columna) ---
def reconcile_data(df_ledger: pd.DataFrame, df_statement: pd.DataFrame, include_ids: bool = True) -> Optional[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """Realiza conciliación automática por monto y contador."""
    try:
        print("\n--- Iniciando reconcile_data (Automática) ---")
        # Validaciones de entrada...
        if df_ledger is None or df_ledger.empty or df_statement is None or df_statement.empty:
            print("WARN reconcile_data: Uno o ambos DataFrames de entrada están vacíos.")
            empty_df = pd.DataFrame()
            return empty_df, empty_df, empty_df

        # Validar columnas Ledger (Contabilidad)
        req_ledger = MIN_COLS_ACCOUNTING[:] # Copiar lista
        if include_ids: req_ledger.append('tx_id_ref') # tx_id_ref se añade en main.py
        if not all(col in df_ledger.columns for col in req_ledger):
            missing = [c for c in req_ledger if c not in df_ledger.columns]
            raise ValueError(f"Faltan columnas requeridas en Ledger: {missing}")

        # Validar columnas Statement (Banco)
        req_stmt = MIN_COLS_BANK[:] # Copiar lista
        if include_ids: req_stmt.append('tx_id_ref')
        if not all(col in df_statement.columns for col in req_stmt):
            missing = [c for c in req_stmt if c not in df_statement.columns]
            raise ValueError(f"Faltan columnas requeridas en Statement: {missing}")

        # Preparar Ledger
        df_ledger_copy = df_ledger.copy()
        # Calcular monto neto para ledger (Débito positivo, Crédito negativo)
        df_ledger_copy[MOVIMIENTO_CONCILIACION] = (
             pd.to_numeric(df_ledger_copy[AUXILIAR_DEBITO], errors='coerce').fillna(0.0) -
             pd.to_numeric(df_ledger_copy[AUXILIAR_CREDITO], errors='coerce').fillna(0.0)
        ).round(2) # Redondear a 2 decimales
        df_ledger_copy = df_ledger_copy.sort_values(by=[MOVIMIENTO_CONCILIACION, FECHA_CONCILIACION]).reset_index(drop=True)
        df_ledger_copy[CONTADOR_CONCILIACION] = df_ledger_copy.groupby(MOVIMIENTO_CONCILIACION).cumcount()
        ledger_cols = [MOVIMIENTO_CONCILIACION, CONTADOR_CONCILIACION, FECHA_CONCILIACION, DOCUMENTO_AUXILIAR, DESCRIPCION_AUXILIAR, AUXILIAR_DEBITO, AUXILIAR_CREDITO]
        if include_ids: ledger_cols.append('tx_id_ref')
        df_ledger_merge = df_ledger_copy[ledger_cols].rename(columns={FECHA_CONCILIACION: f'{FECHA_CONCILIACION}_libro'}) # Renombrar fecha
        print(f"Ledger listo para merge ({len(df_ledger_merge)} filas). Columnas: {list(df_ledger_merge.columns)}")

        # Preparar Statement
        df_statement_copy = df_statement.copy()
        df_statement_copy[MOVIMIENTO_CONCILIACION] = pd.to_numeric(df_statement_copy[MOVIMIENTO_CONCILIACION], errors='coerce').fillna(0.0).round(2) # Redondear
        df_statement_copy = df_statement_copy.sort_values(by=[MOVIMIENTO_CONCILIACION, FECHA_CONCILIACION]).reset_index(drop=True)
        df_statement_copy[CONTADOR_CONCILIACION] = df_statement_copy.groupby(MOVIMIENTO_CONCILIACION).cumcount()
        statement_cols = [MOVIMIENTO_CONCILIACION, CONTADOR_CONCILIACION, FECHA_CONCILIACION, DESCRIPCION_EXTRACTO]
        if include_ids: statement_cols.append('tx_id_ref')
        df_statement_merge = df_statement_copy[statement_cols].rename(columns={FECHA_CONCILIACION: f'{FECHA_CONCILIACION}_extracto'}) # Renombrar fecha
        print(f"Statement listo para merge ({len(df_statement_merge)} filas). Columnas: {list(df_statement_merge.columns)}")

        # Realizar Merge
        merge_keys = [MOVIMIENTO_CONCILIACION, CONTADOR_CONCILIACION]
        print(f"Realizando merge 'outer' en {merge_keys}...")
        reconciled_data = pd.merge(
            df_ledger_merge,
            df_statement_merge,
            on=merge_keys,
            how='outer',
            indicator=True,
            suffixes=('_libro', '_extracto') # Sufijos para columnas con mismo nombre (excepto claves de merge)
        )
        print(f"Merge completado. Dimensiones: {reconciled_data.shape}. Distribución:\n{reconciled_data['_merge'].value_counts()}")

        # Separar resultados
        successful = reconciled_data[reconciled_data['_merge'] == 'both'].copy()
        pending = reconciled_data[reconciled_data['_merge'] != 'both'].copy()

        # Limpiar columnas y renombrar IDs si existen
        successful.drop(columns=[CONTADOR_CONCILIACION, '_merge'], errors='ignore', inplace=True)
        pending.drop(columns=[CONTADOR_CONCILIACION], errors='ignore', inplace=True) # Mantener _merge

        if include_ids:
            # Los IDs 'tx_id_ref' tendrán sufijos _libro y _extracto debido al merge
            # Renombrarlos a _x (libro) y _y (extracto) como esperaba la versión anterior de main.py
            rename_map = {'tx_id_ref_libro': 'tx_id_ref_x', 'tx_id_ref_extracto': 'tx_id_ref_y'}
            successful.rename(columns=rename_map, inplace=True, errors='ignore')
            pending.rename(columns=rename_map, inplace=True, errors='ignore')
            print(f"DEBUG: IDs renombrados a tx_id_ref_x y tx_id_ref_y.")

        print(f"--- Conciliación (Automática) finalizada ---")
        print(f"Conciliados: {len(successful)}")
        print(f"Pendientes Libro (left_only): {len(pending[pending['_merge'] == 'left_only'])}")
        print(f"Pendientes Extracto (right_only): {len(pending[pending['_merge'] == 'right_only'])}")

        return reconciled_data, successful, pending
    except Exception as e:
        print(f"ERROR inesperado en reconcile_data:")
        traceback.print_exc()
        return None

# --- Bloque para ejecución directa (Testing) ---
if __name__ == "__main__":
    print("--- Ejecutando processing.py directamente para prueba ---")

    # Define rutas a tus archivos locales de prueba
    # Asegúrate que estas rutas sean correctas en tu sistema
    ruta_auxiliar_siesa_test = r"G:\Mi unidad\automatizaciones\12_conciliacion_bancaria\siesa_bancolombia_abril_2025.xlsx"
    ruta_extracto_bancolombia_test = r"G:\Mi unidad\automatizaciones\12_conciliacion_bancaria\CSV_27799726048_000000901195703_20250502_08133217.csv"

    # Probar la función genérica
    print("\n--- Probando process_uploaded_file ---")
    df_libro_test = None
    try:
        with open(ruta_auxiliar_siesa_test, 'rb') as f:
            content_siesa = f.read()
        df_libro_test = process_uploaded_file(content_siesa, 'siesa_xlsx')
        if df_libro_test is not None:
            print(f"\nLibro SIESA procesado (genérico): {len(df_libro_test)} filas.")
            print(df_libro_test.head())
            print(df_libro_test.info())
        else:
            print("\nFallo procesando Libro SIESA (genérico).")
    except FileNotFoundError:
        print(f"ERROR: Archivo de prueba SIESA no encontrado en: {ruta_auxiliar_siesa_test}")
    except Exception as e:
        print(f"ERROR al probar SIESA: {e}")

    df_extracto_test = None
    try:
        with open(ruta_extracto_bancolombia_test, 'rb') as f:
            content_bcol = f.read()
        df_extracto_test = process_uploaded_file(content_bcol, 'bancolombia_csv_9col')
        if df_extracto_test is not None:
            print(f"\nExtracto Bancolombia procesado (genérico): {len(df_extracto_test)} filas.")
            print(df_extracto_test.head())
            print(df_extracto_test.info())
        else:
            print("\nFallo procesando Extracto Bancolombia (genérico).")
    except FileNotFoundError:
        print(f"ERROR: Archivo de prueba Bancolombia no encontrado en: {ruta_extracto_bancolombia_test}")
    except Exception as e:
        print(f"ERROR al probar Bancolombia: {e}")


    # Intentar conciliación si ambos se procesaron
    if df_libro_test is not None and not df_libro_test.empty and df_extracto_test is not None and not df_extracto_test.empty:
        print("\n--- Probando reconcile_data ---")
        resultado = reconcile_data(df_libro_test, df_extracto_test, include_ids=False) # Test sin IDs de FastAPI
        if resultado:
            todos_test, conciliados_test, pendientes_test = resultado
            try:
                output_filename_test = 'resultado_conciliacion_prueba_generico.xlsx'
                with pd.ExcelWriter(output_filename_test) as writer:
                    # Escribir hojas con todas las columnas devueltas
                    conciliados_test.to_excel(writer, sheet_name='Conciliados', index=False)
                    pendientes_test.to_excel(writer, sheet_name='Pendientes', index=False)
                    todos_test.to_excel(writer, sheet_name='Todos_Merge', index=False) # Incluir el merge completo
                print(f"\nResultados prueba guardados en '{output_filename_test}'")
            except Exception as e:
                print(f"\nError guardando Excel de prueba: {e}")
        else:
            print("\nFallo la conciliación (prueba).")
    else:
        print("\nNo se pueden conciliar datos (prueba) - uno o ambos archivos fallaron o están vacíos.")

    print("\n--- Fin de la ejecución directa de processing.py ---")
```