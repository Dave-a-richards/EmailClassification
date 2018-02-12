import yaml

with open("categories.yaml", "r") as f:
    try:
        email_categories = yaml.load(f)
        f.close()
    except yaml.YAMLError as exc:
        print('Cannot load categories.yaml')