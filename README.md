POJA CLI
========

A Python CLI to the [POJA stack](https://github.com/hei-school/poja).

# Usage

## Create a completely new project

```
pip install poja
python -m poja \
  --app-name=poja-base \
  --region=eu-west-3 \
  --ssm-sg-id=/poja/sg/id \
  --ssm-subnet1-id=/poja/subnet/public1/id \
  --ssm-subnet2-id=/poja/subnet/public2/id \
  --output-dir=folder-to-be-created
```

Those configurations will be automatically saved in `poja.yml` at the end of the creation.

## Upgrade an already existing project

```
pip install poja --upgrade
python -m poja \
  --app-name=poja-base \
  --region=eu-west-3 \
  --ssm-sg-id=/poja/sg/id \
  --ssm-subnet1-id=/poja/subnet/public1/id \
  --ssm-subnet2-id=/poja/subnet/public2/id \
  --output-dir=folder-already-created
```

Note the `--upgrade` and the `--output-dir=folder-already-created` flags.

The POJA configuration that was used for the previous generation is saved in `poja.yml`: it will be updated after the new upgrade.
