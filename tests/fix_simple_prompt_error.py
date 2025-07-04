#!/usr/bin/env python3
"""
Script para corregir el error de simple_prompt en classify_llm_driven.py
"""
import os
import re

def fix_simple_prompt_error():
    """Corregir el error de simple_prompt en _analyze_with_llm"""
    
    file_path = "nodes/classify_llm_driven.py"
    
    if not os.path.exists(file_path):
        print(f"❌ Archivo no encontrado: {file_path}")
        return False
    
    print("🔧 Corrigiendo error de simple_prompt...")
    
    try:
        # Leer archivo
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Buscar y reemplazar la línea problemática
        old_line = "formatted_prompt = simple_prompt.format(**prompt_input)"
        new_line = "formatted_prompt = continuous_prompt.format(**prompt_input)"
        
        if old_line in content:
            content = content.replace(old_line, new_line)
            print(f"✅ Encontrada y corregida línea: {old_line}")
        else:
            print("⚠️ No se encontró la línea exacta, buscando patrones similares...")
            
            # Buscar patrones más amplios
            patterns = [
                r"formatted_prompt\s*=\s*simple_prompt\.format\(",
                r"simple_prompt\.format\("
            ]
            
            for pattern in patterns:
                if re.search(pattern, content):
                    content = re.sub(pattern, "continuous_prompt.format(", content)
                    print(f"✅ Corregido patrón: {pattern}")
                    break
            else:
                print("❌ No se encontró el patrón de error")
                return False
        
        # Guardar archivo corregido
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Error de simple_prompt corregido exitosamente")
        
        # Verificar que no queden referencias a simple_prompt
        if "simple_prompt" in content:
            print("⚠️ Aún hay referencias a 'simple_prompt' en el archivo")
            lines_with_simple_prompt = []
            for i, line in enumerate(content.split('\n'), 1):
                if "simple_prompt" in line:
                    lines_with_simple_prompt.append(f"Línea {i}: {line.strip()}")
            
            if lines_with_simple_prompt:
                print("📋 Referencias restantes:")
                for ref in lines_with_simple_prompt:
                    print(f"   {ref}")
        else:
            print("✅ No quedan referencias a 'simple_prompt'")
        
        return True
        
    except Exception as e:
        print(f"❌ Error corrigiendo archivo: {e}")
        return False

def validate_prompt_variables():
    """Validar que todas las variables de prompt estén correctamente definidas"""
    
    file_path = "nodes/classify_llm_driven.py"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("\n🔍 Validando variables de prompt...")
        
        # Buscar definiciones de prompts
        prompt_definitions = re.findall(r'(\w+_prompt)\s*=\s*PromptTemplate', content)
        prompt_usages = re.findall(r'(\w+_prompt)\.format\(', content)
        
        print(f"📋 Prompts definidos: {prompt_definitions}")
        print(f"📋 Prompts utilizados: {prompt_usages}")
        
        # Verificar que todos los prompts usados estén definidos
        undefined_prompts = set(prompt_usages) - set(prompt_definitions)
        if undefined_prompts:
            print(f"❌ Prompts utilizados pero no definidos: {undefined_prompts}")
            return False
        else:
            print("✅ Todos los prompts utilizados están correctamente definidos")
            return True
            
    except Exception as e:
        print(f"❌ Error validando prompts: {e}")
        return False

def main():
    """Función principal"""
    print("🔧 CORRECCIÓN DEL ERROR simple_prompt")
    print("=" * 60)
    
    # 1. Corregir el error
    if fix_simple_prompt_error():
        print("\n✅ Corrección aplicada exitosamente")
        
        # 2. Validar que no hay más errores similares
        if validate_prompt_variables():
            print("\n🎉 ¡Todo correcto!")
            print("\n📋 PRÓXIMOS PASOS:")
            print("1. Ejecutar test nuevamente:")
            print("   python -m tests.test_classify_node")
            print("2. O ejecutar tests de refactorización:")
            print("   python -m tests.test_refactored_classify")
        else:
            print("\n⚠️ Hay otros problemas de prompts pendientes")
    else:
        print("\n❌ No se pudo aplicar la corrección automáticamente")
        print("\n📋 CORRECCIÓN MANUAL:")
        print("1. Abrir nodes/classify_llm_driven.py")
        print("2. Buscar 'simple_prompt.format('")
        print("3. Cambiar por 'continuous_prompt.format('")

if __name__ == "__main__":
    main()