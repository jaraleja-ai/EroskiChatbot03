# =====================================================
# database/scripts/process_manual_text.py - Procesar manual sin vectores
# =====================================================
"""
Script para procesar el manual de la balanza DIBAL Mistral
usando búsqueda de texto (sin vectores).
"""

import asyncio
import asyncpg
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import re

# Setup path
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ProcessManual")

class ManualTextProcessor:
    """Procesador de manual técnico usando búsqueda de texto"""
    
    def __init__(self):
        # Configuración de BD
        self.db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", 5432)),
            "database": os.getenv("DB_NAME", "chatbot_db"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "")
        }
        
    @property
    def connection_string(self) -> str:
        """Construir string de conexión"""
        return (f"postgresql://{self.db_config['user']}:{self.db_config['password']}"
                f"@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
    
    async def process_manual(self):
        """Proceso completo de procesamiento del manual"""
        try:
            logger.info("📖 Iniciando procesamiento del manual DIBAL Mistral...")
            
            # 1. Verificar dependencias
            if not self._check_dependencies():
                return False
            
            # 2. Verificar archivo existe
            manual_path = ROOT_DIR / "docs" / "Manual Balanza DIBAL Mistral.pdf"
            if not manual_path.exists():
                logger.error(f"❌ Manual no encontrado: {manual_path}")
                logger.info("💡 Asegúrate de que el archivo esté en docs/")
                return False
            
            # 3. Verificar si ya está procesado
            if await self._is_already_processed(manual_path.name):
                logger.info("✅ Manual ya procesado")
                response = input("¿Deseas re-procesar? (s/n): ").lower().strip()
                if response not in ['s', 'si', 'sí', 'y', 'yes']:
                    return True
                await self._clear_existing_chunks(manual_path.name)
            
            # 4. Procesar PDF
            chunks = await self._process_pdf(manual_path)
            if not chunks:
                return False
            
            # 5. Almacenar chunks
            success = await self._store_chunks(chunks, manual_path.name)
            
            if success:
                logger.info("🎉 Manual procesado exitosamente")
                await self._show_summary()
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ Error procesando manual: {e}")
            return False
    
    def _check_dependencies(self):
        """Verificar que las dependencias están instaladas"""
        try:
            import langchain.document_loaders
            import langchain.text_splitter
            
            logger.info("✅ Dependencias verificadas")
            return True
            
        except ImportError as e:
            logger.error(f"❌ Dependencia faltante: {e}")
            logger.info("💡 Instalar: pip install langchain pypdf2")
            return False
    
    async def _is_already_processed(self, documento_nombre: str) -> bool:
        """Verificar si el documento ya está procesado"""
        try:
            conn = await asyncpg.connect(self.connection_string)
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM knowledge_base WHERE documento_origen = $1",
                documento_nombre
            )
            await conn.close()
            return count > 0
        except Exception as e:
            logger.warning(f"⚠️ Error verificando procesamiento: {e}")
            return False
    
    async def _clear_existing_chunks(self, documento_nombre: str):
        """Limpiar chunks existentes"""
        try:
            conn = await asyncpg.connect(self.connection_string)
            deleted = await conn.fetchval(
                "DELETE FROM knowledge_base WHERE documento_origen = $1 RETURNING COUNT(*)",
                documento_nombre
            )
            await conn.close()
            logger.info(f"🗑️ {deleted} chunks existentes eliminados")
        except Exception as e:
            logger.error(f"❌ Error limpiando chunks: {e}")
    
    async def _process_pdf(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Procesar PDF y crear chunks"""
        try:
            from langchain.document_loaders import PyPDFLoader
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            
            logger.info(f"📄 Cargando PDF: {pdf_path.name}")
            
            # Cargar PDF
            loader = PyPDFLoader(str(pdf_path))
            documents = loader.load()
            
            logger.info(f"📋 Páginas cargadas: {len(documents)}")
            
            # Configurar text splitter optimizado para manuales técnicos
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,  # Tamaño óptimo para búsqueda
                chunk_overlap=200,  # Overlap para preservar contexto
                separators=[
                    "\n\n",  # Párrafos
                    "\n",    # Líneas
                    ". ",    # Oraciones
                    " "      # Palabras
                ],
                length_function=len,
                keep_separator=True
            )
            
            # Crear chunks
            chunks = text_splitter.split_documents(documents)
            
            # Filtrar chunks muy cortos
            filtered_chunks = []
            for chunk in chunks:
                content = chunk.page_content.strip()
                if len(content) >= 50 and not content.isspace():
                    filtered_chunks.append({
                        'content': content,
                        'metadata': chunk.metadata,
                        'page': chunk.metadata.get('page', 0),
                        'source': chunk.metadata.get('source', str(pdf_path))
                    })
            
            logger.info(f"📝 Chunks creados: {len(filtered_chunks)} (filtrados de {len(chunks)})")
            return filtered_chunks
            
        except Exception as e:
            logger.error(f"❌ Error procesando PDF: {e}")
            return []
    
    async def _store_chunks(self, chunks: List[Dict[str, Any]], documento_nombre: str) -> bool:
        """Almacenar chunks en BD (sin vectores)"""
        try:
            import json
            conn = await asyncpg.connect(self.connection_string)
            
            logger.info(f"🔄 Almacenando {len(chunks)} chunks...")
            
            try:
                total_chunks = len(chunks)
                
                for i, chunk in enumerate(chunks, 1):
                    # Progress indicator
                    if i % 10 == 0 or i == total_chunks:
                        logger.info(f"🔄 Procesando chunk {i}/{total_chunks} ({i/total_chunks*100:.1f}%)")
                    
                    # Extraer metadata adicional
                    metadata = self._extract_metadata(chunk['content'], chunk['metadata'])
                    
                    # Insertar en BD (sin embedding)
                    await conn.execute("""
                        INSERT INTO knowledge_base 
                        (documento_origen, chunk_text, pagina_numero, seccion, capitulo, 
                         palabras_clave, chunk_metadata, embedding_pendiente)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, 
                        documento_nombre,
                        chunk['content'],
                        chunk['page'],
                        metadata['seccion'],
                        metadata['capitulo'],
                        metadata['palabras_clave'],
                        json.dumps(metadata),  # Convertir a JSON
                        True  # embedding_pendiente = True
                    )
                
                logger.info("✅ Todos los chunks almacenados")
                return True
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ Error almacenando chunks: {e}")
            return False
    
    def _extract_metadata(self, text: str, original_metadata: Dict) -> Dict[str, Any]:
        """Extraer metadata adicional del texto"""
        metadata = {
            'seccion': self._extract_section(text),
            'capitulo': self._extract_chapter(text),
            'palabras_clave': self._extract_keywords(text),
            'longitud': len(text),
            'es_tabla': self._is_table_content(text),
            'es_lista': self._is_list_content(text),
            'contiene_codigo': self._contains_error_code(text),
            'tipo_contenido': self._classify_content_type(text)
        }
        
        # Agregar metadata original
        metadata.update(original_metadata)
        
        return metadata
    
    def _extract_section(self, text: str) -> str:
        """Extraer nombre de sección del texto"""
        lines = text.split('\n')
        
        for line in lines[:3]:  # Revisar primeras 3 líneas
            line = line.strip()
            
            # Patrones comunes en manuales técnicos
            section_patterns = [
                r'^(\d+\.?\d*\.?\d*)\s+(.+)',  # "1.2.3 Título"
                r'^([A-Z][A-ZÁÉÍÓÚÑÜ\s]+)$',   # "CAPÍTULO MAYÚSCULAS"
                r'.*[Cc]apítulo\s+(\d+)',      # "Capítulo X"
                r'.*[Ss]ección\s+(\d+)',       # "Sección X"
                r'.*[Pp]arte\s+(\d+)',         # "Parte X"
            ]
            
            for pattern in section_patterns:
                match = re.match(pattern, line)
                if match and len(line) < 100:
                    return line[:200]
        
        return "General"
    
    def _extract_chapter(self, text: str) -> str:
        """Extraer capítulo del texto"""
        chapter_patterns = [
            r'[Cc]apítulo\s+(\d+)[:\-\s]*(.{0,50})',
            r'[Cc]hapter\s+(\d+)[:\-\s]*(.{0,50})',
            r'^(\d+)\.\s*([A-ZÁÉÍÓÚÑÜ][^.]{5,50})',
        ]
        
        for pattern in chapter_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)[:200]
        
        return ""
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extraer palabras clave relevantes"""
        keywords = []
        
        # Términos específicos de balanzas DIBAL
        balanza_terms = [
            'balanza', 'peso', 'tara', 'calibrar', 'calibración',
            'etiqueta', 'precio', 'imprimir', 'display', 'teclado',
            'dibal', 'mistral', 'báscula', 'pesaje', 'error',
            'configuración', 'menú', 'función', 'botón', 'pantalla',
            'memoria', 'producto', 'código', 'PLU', 'ticket',
            'impresora', 'conexión', 'cable', 'instalación'
        ]
        
        text_lower = text.lower()
        
        for term in balanza_terms:
            if term in text_lower:
                keywords.append(term)
        
        # Buscar códigos de error
        error_codes = re.findall(r'[Ee]rror?\s*:?\s*(\d+)', text)
        for code in error_codes:
            keywords.append(f"error_{code}")
        
        # Buscar números de modelo
        models = re.findall(r'(DIBAL|dibal)\s+(\w+)', text, re.IGNORECASE)
        for model in models:
            keywords.append(f"modelo_{model[1].lower()}")
        
        return keywords[:10]  # Máximo 10 keywords
    
    def _is_table_content(self, text: str) -> bool:
        """Detectar si el contenido es una tabla"""
        lines = text.split('\n')
        tab_count = sum(1 for line in lines if '\t' in line or '|' in line)
        return tab_count > len(lines) * 0.3
    
    def _is_list_content(self, text: str) -> bool:
        """Detectar si el contenido es una lista"""
        lines = text.split('\n')
        list_indicators = ['-', '•', '*', '1.', '2.', 'a)', 'b)']
        list_count = sum(1 for line in lines 
                        if any(line.strip().startswith(indicator) 
                              for indicator in list_indicators))
        return list_count > len(lines) * 0.5
    
    def _contains_error_code(self, text: str) -> bool:
        """Detectar si contiene códigos de error"""
        error_patterns = [
            r'[Ee]rror\s*:?\s*\d+',
            r'[Cc]ódigo\s*:?\s*\d+',
            r'[Ff]allo\s*:?\s*\d+'
        ]
        
        return any(re.search(pattern, text) for pattern in error_patterns)
    
    def _classify_content_type(self, text: str) -> str:
        """Clasificar tipo de contenido"""
        if self._is_table_content(text):
            return "tabla"
        elif self._is_list_content(text):
            return "lista"
        elif self._contains_error_code(text):
            return "error_code"
        elif any(term in text.lower() for term in ['instalación', 'conexión', 'configurar']):
            return "instalacion"
        elif any(term in text.lower() for term in ['calibrar', 'calibración', 'ajuste']):
            return "calibracion"
        elif any(term in text.lower() for term in ['error', 'problema', 'fallo']):
            return "solucion_problemas"
        else:
            return "general"
    
    async def _show_summary(self):
        """Mostrar resumen del procesamiento"""
        try:
            conn = await asyncpg.connect(self.connection_string)
            
            # Estadísticas generales
            total_chunks = await conn.fetchval(
                "SELECT COUNT(*) FROM knowledge_base"
            )
            
            total_docs = await conn.fetchval(
                "SELECT COUNT(DISTINCT documento_origen) FROM knowledge_base"
            )
            
            # Estadísticas por sección
            sections = await conn.fetch("""
                SELECT seccion, COUNT(*) as chunks
                FROM knowledge_base 
                WHERE seccion != 'General'
                GROUP BY seccion 
                ORDER BY chunks DESC 
                LIMIT 5
            """)
            
            # Estadísticas por tipo de contenido
            content_types = await conn.fetch("""
                SELECT 
                    chunk_metadata->>'tipo_contenido' as tipo,
                    COUNT(*) as chunks
                FROM knowledge_base 
                WHERE chunk_metadata->>'tipo_contenido' IS NOT NULL
                GROUP BY chunk_metadata->>'tipo_contenido'
                ORDER BY chunks DESC
            """)
            
            await conn.close()
            
            logger.info("📊 RESUMEN DEL PROCESAMIENTO:")
            logger.info(f"   📚 Documentos procesados: {total_docs}")
            logger.info(f"   📄 Total chunks: {total_chunks}")
            
            if sections:
                logger.info("   🔍 Top secciones:")
                for section in sections:
                    logger.info(f"      • {section['seccion']}: {section['chunks']} chunks")
            
            if content_types:
                logger.info("   📋 Tipos de contenido:")
                for ctype in content_types:
                    logger.info(f"      • {ctype['tipo']}: {ctype['chunks']} chunks")
            
            logger.info("\n🎯 PRÓXIMOS PASOS:")
            logger.info("   1. 🧪 Probar búsqueda: python database/scripts/test_text_search.py")
            logger.info("   2. 🚀 Ejecutar chatbot: python main.py")
            
        except Exception as e:
            logger.warning(f"⚠️ Error mostrando resumen: {e}")

async def main():
    """Entry point del script"""
    # Cargar variables de entorno
    current_dir = Path(__file__).parent
    root_dir = current_dir.parent.parent
    env_file = root_dir / ".env"
    
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"\'')
    
    print("📖 Procesador de Manual DIBAL Mistral")
    print("=" * 45)
    print("🔍 MÉTODO: Búsqueda de texto")
    print("📚 SIN VECTORES: Funcional y eficiente")
    print("=" * 45)
    
    processor = ManualTextProcessor()
    success = await processor.process_manual()
    
    if success:
        print("\n✅ ¡Manual procesado exitosamente!")
    else:
        print("\n❌ Error en el procesamiento")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())