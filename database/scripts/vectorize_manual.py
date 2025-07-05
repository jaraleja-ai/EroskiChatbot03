# =====================================================
# scripts/vectorize_manual.py - Vectorización del manual DIBAL
# =====================================================
"""
Script para vectorizar el manual de la balanza DIBAL Mistral
y almacenarlo en PostgreSQL con pgvector para RAG.
"""

import asyncio
import asyncpg
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import json
import re

# Setup path
ROOT_DIR = Path(__file__).parent.parent.parent  # Subir tres niveles: scripts -> database -> raíz
sys.path.insert(0, str(ROOT_DIR))

from config.settings import get_settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("VectorizeManual")

class ManualVectorizer:
    """Vectorizador de manual técnico con soporte Azure OpenAI"""
    
    def __init__(self):
        self.settings = get_settings()
        self.openai_client = None
        self.embedding_deployment = None
        
    async def vectorize_manual(self):
        """Proceso completo de vectorización"""
        try:
            logger.info("📖 Iniciando vectorización del manual DIBAL Mistral...")
            
            # 1. Verificar dependencias
            if not self._check_dependencies():
                return False
            
            # 2. Verificar archivo existe
            manual_path = ROOT_DIR / "docs" / "Manual Balanza DIBAL Mistral.pdf"
            if not manual_path.exists():
                logger.error(f"❌ Manual no encontrado: {manual_path}")
                logger.info("💡 Asegúrate de que el archivo esté en docs/")
                return False
            
            # 3. Verificar si ya está vectorizado
            if await self._is_already_vectorized(manual_path.name):
                logger.info("✅ Manual ya vectorizado")
                response = input("¿Deseas re-vectorizar? (s/n): ").lower().strip()
                if response not in ['s', 'si', 'sí', 'y', 'yes']:
                    return True
                await self._clear_existing_vectors(manual_path.name)
            
            # 4. Procesar PDF
            chunks = await self._process_pdf(manual_path)
            if not chunks:
                return False
            
            # 5. Vectorizar y almacenar
            success = await self._vectorize_and_store(chunks, manual_path.name)
            
            if success:
                logger.info("🎉 Manual vectorizado exitosamente")
                await self._show_summary()
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ Error en vectorización: {e}")
            return False
    
    def _check_dependencies(self):
        """Verificar que las dependencias están instaladas"""
        try:
            import langchain.document_loaders
            import langchain.text_splitter
            from openai import AzureOpenAI
            
            # Verificar configuración Azure OpenAI
            api_key = os.getenv('LLM_AZURE_OPENAI_API_KEY')
            endpoint = os.getenv('LLM_AZURE_OPENAI_ENDPOINT')
            api_version = os.getenv('LLM_AZURE_API_VERSION')
            embedding_deployment = os.getenv('LLM_AZURE_EMBEDDING_DEPLOYMENT')
            
            if not all([api_key, endpoint, api_version, embedding_deployment]):
                logger.error("❌ Configuración Azure OpenAI incompleta")
                logger.info("💡 Verificar variables en .env:")
                logger.info("   - LLM_AZURE_OPENAI_API_KEY")
                logger.info("   - LLM_AZURE_OPENAI_ENDPOINT") 
                logger.info("   - LLM_AZURE_API_VERSION")
                logger.info("   - LLM_AZURE_EMBEDDING_DEPLOYMENT")
                return False
            
            # Crear cliente Azure OpenAI
            self.openai_client = AzureOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version=api_version
            )
            
            # Guardar nombre del deployment para embeddings
            self.embedding_deployment = embedding_deployment.strip()
            
            logger.info("✅ Cliente Azure OpenAI configurado")
            logger.info(f"📍 Endpoint: {endpoint}")
            logger.info(f"📍 Deployment embeddings: {self.embedding_deployment}")
            return True
            
        except ImportError as e:
            logger.error(f"❌ Dependencia faltante: {e}")
            logger.info("💡 Instalar: pip install langchain pypdf2 openai")
            return False
    
    async def _is_already_vectorized(self, documento_nombre: str) -> bool:
        """Verificar si el documento ya está vectorizado"""
        connection_string = self._get_connection_string()
        
        try:
            conn = await asyncpg.connect(connection_string)
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM knowledge_base WHERE documento_origen = $1",
                documento_nombre
            )
            await conn.close()
            return count > 0
        except Exception as e:
            logger.warning(f"⚠️ Error verificando vectorización: {e}")
            return False
    
    async def _clear_existing_vectors(self, documento_nombre: str):
        """Limpiar vectores existentes"""
        connection_string = self._get_connection_string()
        
        try:
            conn = await asyncpg.connect(connection_string)
            # Corregir: usar DELETE simple sin RETURNING COUNT(*)
            await conn.execute(
                "DELETE FROM knowledge_base WHERE documento_origen = $1",
                documento_nombre
            )
            
            # Contar después para obtener feedback
            remaining = await conn.fetchval(
                "SELECT COUNT(*) FROM knowledge_base WHERE documento_origen = $1",
                documento_nombre
            )
            
            await conn.close()
            logger.info(f"🗑️ Chunks existentes eliminados (quedan: {remaining})")
        except Exception as e:
            logger.error(f"❌ Error limpiando vectores: {e}")
    
    async def _process_pdf(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Procesar PDF y crear chunks"""
        try:
            from langchain_community.document_loaders import PyPDFLoader
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            
            logger.info(f"📄 Cargando PDF: {pdf_path.name}")
            
            # Cargar PDF
            loader = PyPDFLoader(str(pdf_path))
            documents = loader.load()
            
            logger.info(f"📋 Páginas cargadas: {len(documents)}")
            
            # Configurar text splitter optimizado para manuales técnicos
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,  # Tamaño óptimo para embeddings
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
            
            # Filtrar chunks muy cortos o que solo contienen espacios
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
    
    async def _vectorize_and_store(self, chunks: List[Dict[str, Any]], documento_nombre: str) -> bool:
        """Vectorizar chunks y almacenar en BD"""
        try:
            connection_string = self._get_connection_string()
            conn = await asyncpg.connect(connection_string)
            
            logger.info(f"🔄 Vectorizando {len(chunks)} chunks...")
            
            try:
                total_chunks = len(chunks)
                
                for i, chunk in enumerate(chunks, 1):
                    # Progress indicator
                    if i % 10 == 0 or i == total_chunks:
                        logger.info(f"🔄 Procesando chunk {i}/{total_chunks} ({i/total_chunks*100:.1f}%)")
                    
                    # Generar embedding
                    embedding = await self._generate_embedding(chunk['content'])
                    if not embedding:
                        logger.warning(f"⚠️ No se pudo generar embedding para chunk {i}")
                        continue
                    
                    # Extraer metadata adicional
                    metadata = self._extract_metadata(chunk['content'], chunk['metadata'])
                    
                    # Insertar en BD con vector convertido
                    await conn.execute("""
                        INSERT INTO knowledge_base 
                        (documento_origen, chunk_text, chunk_embedding, pagina_numero, 
                         seccion, capitulo, palabras_clave, chunk_metadata)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, 
                        documento_nombre,
                        chunk['content'],
                        str(embedding),  # Convertir lista a string para PostgreSQL
                        chunk['page'],
                        metadata['seccion'],
                        metadata['capitulo'],
                        metadata['palabras_clave'],
                        json.dumps(metadata)
                    )
                
                logger.info("✅ Todos los chunks vectorizados y almacenados")
                return True
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ Error vectorizando: {e}")
            return False
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generar embedding usando Azure OpenAI"""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_deployment,  # Usar deployment de Azure
                input=text,
                encoding_format="float"
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"❌ Error generando embedding: {e}")
            logger.error(f"📍 Deployment usado: {self.embedding_deployment}")
            return None
    
    def _extract_metadata(self, text: str, original_metadata: Dict) -> Dict[str, Any]:
        """Extraer metadata adicional del texto"""
        metadata = {
            'seccion': self._extract_section(text),
            'capitulo': self._extract_chapter(text),
            'palabras_clave': self._extract_keywords(text),
            'longitud': len(text),
            'es_tabla': self._is_table_content(text),
            'es_lista': self._is_list_content(text),
            'contiene_codigo': self._contains_error_code(text)
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
                if match and len(line) < 100:  # No muy largo
                    return line[:200]  # Truncar si es muy largo
        
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
            'memoria', 'producto', 'código', 'PLU', 'ticket'
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
    
    def _get_connection_string(self) -> str:
        """Construir string de conexión"""
        db_config = self.settings.database
        return (
            f"postgresql://{db_config.user}:{db_config.password}"
            f"@{db_config.host}:{db_config.port}/{db_config.name}"
        )
    
    async def _show_summary(self):
        """Mostrar resumen de la vectorización"""
        connection_string = self._get_connection_string()
        
        try:
            conn = await asyncpg.connect(connection_string)
            
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
            
            await conn.close()
            
            logger.info("📊 RESUMEN DE VECTORIZACIÓN:")
            logger.info(f"   📚 Documentos procesados: {total_docs}")
            logger.info(f"   📄 Total chunks: {total_chunks}")
            
            if sections:
                logger.info("   🔍 Top secciones:")
                for section in sections:
                    logger.info(f"      • {section['seccion']}: {section['chunks']} chunks")
            
            logger.info("\n🎯 PRÓXIMOS PASOS:")
            logger.info("   1. 🧪 Probar búsqueda: python -m scripts.test_rag")
            logger.info("   2. 🚀 Ejecutar chatbot: python main.py")
            
        except Exception as e:
            logger.warning(f"⚠️ Error mostrando resumen: {e}")

async def main():
    """Entry point del script"""
    print("📖 Vectorizador de Manual DIBAL Mistral")
    print("=" * 45)
    
    vectorizer = ManualVectorizer()
    success = await vectorizer.vectorize_manual()
    
    if success:
        print("\n✅ ¡Vectorización completada exitosamente!")
    else:
        print("\n❌ Error en la vectorización")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())