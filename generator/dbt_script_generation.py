import yaml
import os

# ==========================================
# 1. Configuration Paths
# ==========================================
# Path to your custom YAML file
yaml_path = 'generator/data_vault_metadata.yml'

# Directory where the dbt SQL files will be saved
output_dir = 'models/raw_vault'

# Ensure the output directory exists before writing files
os.makedirs(output_dir, exist_ok=True)

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
        # Otherwise, wrap it in quotes as a string
        if isinstance(value, list):
            val_str = str(value)  # Python lists convert cleanly to Jinja lists: ['A', 'B']
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
        
    else:
        print(f"Warning: Unknown type '{dv_type}' for model '{model_name}'. Skipping.")
        continue

    # ==========================================
    # 4. Write the SQL file
    # ==========================================
    file_path = os.path.join(output_dir, f"{model_name}.sql")
    with open(file_path, 'w') as f:
        f.write(sql)
    
    print(f"Generated: {file_path}")

print("\nSuccess! All Data Vault models have been generated.")