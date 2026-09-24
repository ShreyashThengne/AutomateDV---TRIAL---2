import yaml
import os
import json
import sys

# ==========================================
# 1. Configuration Paths
# ==========================================
yaml_path = 'generator/data_vault_metadata.yml'
base_output_dir = 'models/raw_vault'

folder_mapping = {
    'hub': 'hubs',
    'link': 'links',
    'satellite': 'sats',
    't_link': 't_links'
}

# ==========================================
# 2. Load the YAML Metadata
# ==========================================
with open(yaml_path, 'r') as file:
    dv_config = yaml.safe_load(file) or {}

models = dv_config.get('models') or {}

expected_files = set() 
schema_docs = {
    'hubs': {'version': 2, 'models': []},
    'links': {'version': 2, 'models': []},
    'sats': {'version': 2, 'models': []},
    't_links': {'version': 2, 'models': []}
}

# Buffer dictionary to hold file contents in memory before writing
files_to_write = {}

# ==========================================
# 3. Validations and Memory Generation
# ==========================================
for model_name, config in models.items():
    dv_type = config.get('type')
    subfolder_name = folder_mapping.get(dv_type)
    
    if not subfolder_name:
        print(f"Warning: Unknown type '{dv_type}' for model '{model_name}'. Skipping.")
        continue

    # Validation: Catch errors BEFORE touching the disk
    if dv_type == 'satellite' and isinstance(config.get('source_model'), list):
        print(f"ERROR: Satellite '{model_name}' cannot have multiple source_models. Must be a string. Exiting without making changes.")
        sys.exit(1)
        
    model_dir = os.path.join(base_output_dir, subfolder_name)
    file_path = os.path.join(model_dir, f"{model_name}.sql")
    expected_files.add(file_path)

    # --- A. Build dbt Schema/Test logic ---
    src_pk = config.get('src_pk')
    src_ldts = config.get('src_ldts')
    
    if src_pk:
        model_test_entry = {'name': model_name, 'columns': []}
        
        if dv_type in ['hub', 'link', 't_link']:
            model_test_entry['columns'].append({'name': src_pk, 'tests': ['unique', 'not_null']})
            
        elif dv_type == 'satellite':
            model_test_entry['columns'].append({'name': src_pk, 'tests': ['not_null']})
            if src_ldts:
                model_test_entry['tests'] = [
                    {'dbt_utils.unique_combination_of_columns': {'combination_of_columns': [src_pk, src_ldts]}}
                ]
            
        schema_docs[subfolder_name]['models'].append(model_test_entry)

    # --- B. Build SQL Generation logic ---
    materialized = config.get('materialized', 'incremental')
    schema = config.get('schema', 'raw_vault')
    tags = config.get('tags', [])
    
    sql = f"{{{{ config(materialized='{materialized}', schema='{schema}', tags={tags}) }}}}\n\n"
    
    for key, value in config.items():
        if key in ['type', 'materialized', 'schema', 'tags']: continue
        val_str = json.dumps(value) if isinstance(value, list) else f'"{value}"'
        sql += f"{{%- set {key} = {val_str} -%}}\n"
        
    sql += "\n"
    
    if dv_type == 'hub': sql += "{{ automate_dv.hub(src_pk=src_pk, src_nk=src_nk, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}\n"
    elif dv_type == 'link': sql += "{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}\n"
    elif dv_type == 'satellite': sql += "{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload, src_eff=src_eff, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}\n"
    elif dv_type == 't_link': sql += "{{ automate_dv.t_link(src_pk=src_pk, src_fk=src_fk, src_payload=src_payload, src_eff=src_eff, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}\n"

    # Store the SQL in memory instead of writing it
    files_to_write[file_path] = sql

# ==========================================
# 4. Commit to Disk (Only runs if no errors occurred)
# ==========================================
# Ensure directories exist
for folder in folder_mapping.values():
    os.makedirs(os.path.join(base_output_dir, folder), exist_ok=True)

# Write the SQL files
for file_path, sql in files_to_write.items():
    needs_update = True 
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            if f.read() == sql: needs_update = False
            
    if needs_update:
        with open(file_path, 'w') as f: f.write(sql)
        print(f"Updated SQL: {file_path}")

# Write schema.yml files
for folder, schema_data in schema_docs.items():
    if schema_data['models']:
        schema_path = os.path.join(base_output_dir, folder, 'schema.yml')
        expected_files.add(schema_path) 
        
        with open(schema_path, 'w') as f:
            yaml.dump(schema_data, f, sort_keys=False, default_flow_style=False)
        print(f"Updated Tests: {schema_path}")

# ==========================================
# 5. Clean up orphaned files
# ==========================================
if os.path.exists(base_output_dir):
    for root, dirs, files in os.walk(base_output_dir):
        for file in files:
            if file.endswith('.sql') or file == 'schema.yml':
                current_file_path = os.path.join(root, file)
                if current_file_path not in expected_files:
                    os.remove(current_file_path)
                    print(f"Deleted orphaned file: {current_file_path}")

print("\nSuccess! Data Vault models and schema tests generated.")