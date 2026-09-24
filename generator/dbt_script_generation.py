import yaml
import os
import json

# ==========================================
# 1. Configuration Paths
# ==========================================
# Path to your custom YAML file
yaml_path = 'generator/data_vault_metadata.yml'

# Base directory where the dbt SQL folders will be created
base_output_dir = 'models/raw_vault'

# Folder mapping based on Data Vault type
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
    dv_config = yaml.safe_load(file)

models = dv_config.get('models', {})

# ==========================================
# 3. Generate SQL for each model
# ==========================================
for model_name, config in models.items():
    dv_type = config.get('type')
    
    # Determine which subfolder this model belongs to
    subfolder_name = folder_mapping.get(dv_type)
    
    if not subfolder_name:
        print(f"Warning: Unknown type '{dv_type}' for model '{model_name}'. Skipping.")
        continue
        
    # Ensure the specific subfolder exists (e.g., models/raw_vault/hubs)
    model_dir = os.path.join(base_output_dir, subfolder_name)
    os.makedirs(model_dir, exist_ok=True)

    # Extract dbt config properties (with safe defaults)
    materialized = config.get('materialized', 'incremental')
    schema = config.get('schema', 'raw_vault')
    tags = config.get('tags', [])
    
    # Start building the SQL string with the dbt config block
    sql = f"{{{{ config(materialized='{materialized}', schema='{schema}', tags={tags}) }}}}\n\n"
    
    # Dynamically build the Jinja variable assignments
    for key, value in config.items():
        # Skip the metadata keys that belong in the config block or are used for routing
        if key in ['type', 'materialized', 'schema', 'tags']:
            continue
        
        # If the value is a list (like src_payload or src_fk), format it as a Jinja list
        if isinstance(value, list):
            val_str = json.dumps(value)  # <-- Forces double quotes: ["A", "B"]
        else:
            val_str = f'"{value}"'
            
        sql += f"{{%- set {key} = {val_str} -%}}\n"
        
    sql += "\n"
    
    # Append the correct automate_dv macro based on the model type
    if dv_type == 'hub':
        sql += "{{ automate_dv.hub(src_pk=src_pk, src_nk=src_nk, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}\n"
        
    elif dv_type == 'link':
        sql += "{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}\n"
        
    elif dv_type == 'satellite':
        sql += "{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload, src_eff=src_eff, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}\n"
        
    elif dv_type == 't_link':
        sql += "{{ automate_dv.t_link(src_pk=src_pk, src_fk=src_fk, src_payload=src_payload, src_eff=src_eff, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}\n"

    # ==========================================
    # 4. Write the SQL file
    # ==========================================
    file_path = os.path.join(model_dir, f"{model_name}.sql")
    with open(file_path, 'w') as f:
        f.write(sql)
    
    print(f"Generated: {file_path}")

print("\nSuccess! All Data Vault models have been generated into their respective folders.")