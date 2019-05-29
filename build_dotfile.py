#!/usr/bin/env python
import argparse
from sqlalchemy import create_engine
from sqlalchemy import MetaData
from jinja2 import Template
import inflect
import attr
from graphviz import Digraph, Graph, Source


@attr.s
class Table(object):
    name = attr.ib()
    columns = attr.ib()
    indices = attr.ib()
    constraints = attr.ib()
    foreign_keys = attr.ib()
    potential_foreign_keys = attr.ib()


@attr.s
class Column(object):
    name = attr.ib()
    type = attr.ib()


@attr.s
class Index(object):
    name = attr.ib()


@attr.s
class Constraint(object):
    name = attr.ib()


@attr.s
class ForeignKey(object):
    src_table = attr.ib()
    src_column = attr.ib()
    dest_table = attr.ib()
    dest_column = attr.ib()

    def __eq__(self, other):
        if self.src_table == other.src_table and self.src_column == other.src_column and self.dest_table == other.dest_table and self.dest_colum == other.dest_column:
            return True
        return False


def resolve_potential_foreign_keys(tables, potential_foreign_keys):
    engine = inflect.engine()
    resolved_foreign_keys = []
    for p in potential_foreign_keys:
        t = [t for t in tables if t.name == p.dest_table or t.name == engine.plural(p.dest_table)]
        if len(t) == 1:
            k = ForeignKey(src_table=p.src_table, src_column=p.src_column, dest_table=t[0].name, dest_column=p.dest_column)
            resolved_foreign_keys.append(k)

    return resolved_foreign_keys


def build(postgres_uri):
    table_list = []
    engine = create_engine(postgres_uri)
    meta = MetaData()
    meta.reflect(bind=engine)
    tables = meta.tables.values()

    foreign_keys = []
    potential_foreign_keys = []

    for table in tables:
        t = Table(name=str(table), columns=[], foreign_keys=[], indices=[], constraints=[], potential_foreign_keys=[])
        table_list.append(t)
        for column in table.columns:
            c = Column(name=column.name, type=column.type)
            t.columns.append(c)
            if len(column.foreign_keys) > 0:
                for foreign_key in column.foreign_keys:
                    dest_table, dest_column = str(foreign_key.column).split('.')
                    k = ForeignKey(src_table=table.name, src_column=column.name, dest_table=dest_table, dest_column=dest_column)
                    foreign_keys.append(k)

            if column.name.split('_')[-1] == 'id':
                dest_table = '_'.join(column.name.split('_')[0:-1])
                k = ForeignKey(src_table=table.name, src_column=column.name, dest_table=dest_table,
                               dest_column='id')
                potential_foreign_keys.append(k)

        for index in table.indexes:
            idx = Index(name=index.name)
            t.indices.append(idx)

        for constraint in table.constraints:
            c = Constraint(name=constraint.name)
            t.constraints.append(c)

    # remove the foreign keys the ended up in both lists
    resolved_keys = resolve_potential_foreign_keys(table_list, potential_foreign_keys)
    resolved_keys = [r for r in resolved_keys if r not in foreign_keys]
    return table_list, foreign_keys, resolved_keys


parser = argparse.ArgumentParser()
parser.add_argument("postgres_uri", help='URI Of the database to process.')
parser.add_argument('--out', help="--out <output file>", default="out.svg")

if __name__ == '__main__':
    args = parser.parse_args()
    tables, foreign_keys, potential_foreign_keys = build(args.postgres_uri)

    with open('./templates/dot.jinja') as template_file:
        template = Template(template_file.read())
        rendered_template = template.render(tables=tables, foreign_keys=foreign_keys, potential_foreign_keys=potential_foreign_keys)
        src = Source(rendered_template, format='svg')
        out_file = args.out if '.svg' not in args.out else '.'.join(args.out.split('.')[0:-1])
        src.render(f'./{out_file}')

