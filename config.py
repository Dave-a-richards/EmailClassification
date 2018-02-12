import yaml

with open("config.yaml", "r") as f:
    try:
        settings = yaml.load(f)
        f.close()
    except yaml.YAMLError as exc:
        print('Cannot load config.yaml')
