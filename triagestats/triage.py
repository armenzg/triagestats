# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from copy import deepcopy
from dateutil.relativedelta import relativedelta
from itertools import accumulate
from jinja2 import Environment, FileSystemLoader
import json
from libmozdata.bugzilla import Bugzilla
import os
import requests
from shutil import copyfile
import time
from .logger import logger
from .team import get_teams
from . import utils


TYPES = ['created', 'resolved']
SEVERITIES = {'blocker': 'blocker+critical+major',
              'critical': 'blocker+critical+major',
              'major': 'blocker+critical+major',
              'normal': 'normal',
              'minor': 'minor+trivial',
              'trivial': 'minor+trivial'}

HAND_FIX = {'dao+bmo@mozilla.com': 'dao@mozilla.com',
            'krupa.mozbugs@gmail.com': 'kraj@mozilla.com',
            'nobody@mozilla.com': '',
            'spenades@mozilla.com': 'sole@mozilla.com'}


def get_triage_owner(product, component, cache={}, path='data'):
    if product in cache:
        return cache[product].get(component, '')

    if not os.path.isdir(path):
        os.makedirs(path)

    path = '{}/triage_owners.json'.format(path)

    if os.path.isfile(path):
        with open(path, 'r') as In:
            cache.update(json.load(In))
        if product in cache:
            return cache[product].get(component, '')

    r = requests.get('https://bugzilla.mozilla.org/rest/product/' + product)
    products = r.json()['products']
    if not products:
        cache[product] = {}
    else:
        for prod in products:
            p = prod['name']
            cache[p] = cache_p = {}
            for comp in prod['components']:
                owner = comp['triage_owner']
                c = comp['name']
                cache_p[c] = owner

    with open(path, 'w') as Out:
        json.dump(cache, Out, sort_keys=True, indent=4, separators=(',', ': '))

    mail = cache[product].get(component, '')

    return HAND_FIX.get(mail, mail)


def add_triage_owner(data):
    logger.info('Add triage owner: ...')
    res = {}
    for k, v in data.items():
        owner = get_triage_owner(v['product'], v['component'])
        if owner:
            v = deepcopy(v)
            v['triage_owner'] = owner
            res[k] = v

    logger.info('Add triage owner: Ok.')
    return res


def get_cached_raw_data(path='data'):
    res = {}
    for typ in TYPES:
        fpath = '{}/{}_triage_owners.json'.format(path, typ)
        if os.path.isfile(fpath):
            with open(fpath, 'r') as In:
                res[typ] = json.load(In)
    if len(res.keys()) == len(TYPES):
        return res

    return {}


def get_min_max_dates(path='data'):
    data = get_cached_raw_data(path=path)
    min_date = max_date = None
    for typ, i in data.items():
        field = 'creation_time' if typ == 'created' else 'cf_last_resolved'
        for j in i.values():
            date = utils.get_date(j[field])
            if max_date is None or date > max_date:
                max_date = date
                if min_date is None or date < min_date:
                    min_date = date

    return min_date, max_date


def get_dates(start_date, end_date, path='data'):
    if start_date and end_date:
        return utils.get_date(start_date), utils.get_date(end_date)

    m, M = get_min_max_dates(path=path)
    if m is None:
        # no data in cache
        return utils.get_date('2015-01-01'), utils.get_date('today')

    if start_date:
        start_date = utils.get_date(start_date)
        if start_date < m:
            return start_date, m
        if start_date > M:
            return M, start_date
        return start_date, utils.get_date('today')

    if end_date:
        end_date = utils.get_date(end_date)
        if end_date < m:
            return end_date, m
        if end_date > M:
            return M, end_date
        return m, end_date

    return M, utils.get_date('today')


def get_bugs(typ, start_date, end_date):

    def bug_handler(bug, data):
        bugid = bug['id']
        del bug['id']
        data[str(bugid)] = bug

    start_date = utils.get_date(start_date)
    final_date = utils.get_date(end_date) + relativedelta(days=1)
    data = {}
    queries = []
    params = {
        'o1': 'greaterthaneq',
        'o2': 'lessthan',
        'f3': 'bug_severity',
        'o3': 'notequals',
        'v3': 'enhancement',
        'f4': 'keywords',
        'o4': 'notsubstring',
        'v4': 'meta',
        'f5': 'classification',
        'o5': 'notequals',
        'v5': 'Graveyard',
    }
    fields = ['id', 'product', 'component',
              'creation_time', 'severity', 'keywords']

    if typ == 'created':
        params['f1'] = params['f2'] = 'creation_ts'
        params['include_fields'] = fields,
    else:
        params['f1'] = params['f2'] = 'cf_last_resolved'
        params['f6'] = 'resolution'
        params['o6'] = 'isnotempty'
        params['include_fields'] = fields + ['cf_last_resolved'],

    while start_date <= final_date:
        end_date = start_date + relativedelta(days=15)
        params = params.copy()
        params['v1'] = start_date
        params['v2'] = end_date

        logger.info('{}: From {} To {}'.format(typ, start_date, end_date))

        queries.append(Bugzilla(params,
                                bughandler=bug_handler,
                                bugdata=data,
                                timeout=960))
        start_date = end_date

        # Don't nag bugzilla too much
        time.sleep(5)

    for q in queries:
        q.get_data().wait()

    return data


def collect_owners(data):
    owners = {}
    for typ, i in data.items():
        for j in i.values():
            pc = j['product'] + '::' + j['component']
            owner = j['triage_owner']
            if owner not in owners:
                owners[owner] = ['Global', pc]
            else:
                owners[owner].append(pc)
    return owners


def get_data(start_date=None, end_date=None, path='data', from_cache=False):
    cached = get_cached_raw_data(path=path)
    if from_cache and cached:
        return cached

    res = {}
    start_date, end_date = get_dates(start_date, end_date)
    for typ in TYPES:
        data = get_bugs(typ, start_date, end_date)
        data = add_triage_owner(data)
        data.update(cached.get(typ, {}))

        fpath = '{}/{}_triage_owners.json'.format(path, typ)
        with open(fpath, 'w') as Out:
            json.dump(data, Out, sort_keys=True, indent=4, separators=(',', ': '))

        res[typ] = data

    return res


def make_stats(start_date=None, end_date=None, path='data', from_cache=False):
    if from_cache:
        fpath = '{}/stats_by_triage_owners.json'.format(path)
        if os.path.isfile(fpath):
            with open(fpath, 'r') as In:
                return json.load(In)

    start_date, end_date = get_dates(start_date, end_date)
    data = get_data(start_date=start_date, end_date=end_date, path=path, from_cache=False)
    owners = collect_owners(data)
    min_date, max_date = get_min_max_dates(path=path)
    sevs = set(SEVERITIES.values())
    sevs.add('all')

    months = [0] * utils.get_num_months(min_date, max_date)
    months_labels = utils.get_months_labels(min_date, max_date)
    base = {sev: deepcopy(months) for sev in sevs}
    raw = {owner: {pc: deepcopy(base) for pc in pcs} for owner, pcs in owners.items()}

    for typ, info in data.items():
        field = 'creation_time' if typ == 'created' else 'cf_last_resolved'
        x = 1 if typ == 'created' else -1
        for v in info.values():
            pc = v['product'] + '::' + v['component']
            owner = v['triage_owner']
            sev = SEVERITIES[v['severity']]
            date = utils.get_date(v[field])
            index = utils.get_months_index(min_date, date)
            raw[owner][pc][sev][index] += x
            raw[owner][pc]['all'][index] += x
            raw[owner]['Global'][sev][index] += x
            raw[owner]['Global']['all'][index] += x

    cumulate = {}
    for owner, i in raw.items():
        cumulate[owner] = cumulate_o = {}
        for pc, j in i.items():
            cumulate_o[pc] = cumulate_op = {}
            for sev, nums in j.items():
                cumulate_op[sev] = list(accumulate(nums))

    res = {'raw': raw,
           'cumulate': cumulate,
           'labels': months_labels}

    path = '{}/stats_by_triage_owners.json'.format(path)
    with open(path, 'w') as Out:
        json.dump(res, Out, sort_keys=True, indent=4, separators=(',', ': '))

    return res


def add_owner_data(d, data):
    data = data.get('Global', data)
    if 'all' not in d:
        # init d
        d.update(data)
        return

    for sev, numbers in data.items():
        d[sev] = [x + y for x, y in zip(numbers, d[sev])]


def make_team_stats(start_date=None, end_date=None, path='data'):
    data = make_stats(start_date=start_date, end_date=end_date, from_cache=False)
    people = get_teams()
    managers = people['managers']
    ranks = people['ranks']
    persons = people['persons']
    raw = data['raw']
    cumulate = data['cumulate']
    labels = data['labels']
    res = {}
    teams = {persons[m]: [persons[x] for x in t] for m, t in managers.items()}

    for ranked in ranks[1:]:
        for manager in ranked:
            r = {}
            c = {}
            if manager in raw:
                add_owner_data(r, raw[manager])
                add_owner_data(c, cumulate[manager])

            for person in managers[manager]:
                if person in res:
                    add_owner_data(r, res[person]['raw'])
                    add_owner_data(c, res[person]['cumulate'])
                elif person in raw:
                    add_owner_data(r, raw[person])
                    add_owner_data(c, cumulate[person])

            if r:
                res[manager] = {'raw': r,
                                'cumulate': c}

    _res = {}
    for manager, info in res.items():
        _res[persons[manager]] = info
    managers = _res

    owners = {}
    for person, info in raw.items():
        if person in persons:
            owners[persons[person]] = {'raw': info,
                                       'cumulate': cumulate[person]}

    res = {'managers': managers,
           'owners': owners,
           'teams': teams,
           'labels': labels}

    path = '{}/triage_backlog.json'.format(path)
    with open(path, 'w') as Out:
        json.dump(res, Out, sort_keys=True, indent=4, separators=(',', ': '))

    return res


def get_backlog(path='data'):
    path = '{}/triage_backlog.json'.format(path)
    with open(path, 'r') as In:
        return json.load(In)


def make_tree_for_manager(manager, teams, people, cache):
    if manager in cache:
        return cache[manager]

    res = []
    if manager in teams:
        for p in sorted(teams[manager]):
            if p in people:
                res.append(make_tree_for_manager(p, teams, people, cache))
    res = [manager, res]
    cache[manager] = res
    return res


def make_all_tree(teams, people):
    cache = {}
    for person in teams.keys():
        make_tree_for_manager(person, teams, people, cache)
    return cache


def get_person_to_manager(teams):
    res = {}
    for manager, team in teams.items():
        for person in team:
            res[person] = manager
    return res


def get_url_for_pc(pc):
    p, c = pc.split('::')
    params = {'f1': 'bug_severity',
              'o1': 'notequals',
              'v1': 'enhancement',
              'f2': 'keywords',
              'o2': 'notsubstring',
              'v2': 'meta',
              'f3': 'product',
              'o3': 'equals',
              'v3': p,
              'f4': 'component',
              'o4': 'equals',
              'v4': c,
              'f5': 'resolution',
              'o5': 'isempty'}
    params = sorted(params.items(), key=lambda p: (p[0][1], p[0][0], p[1]))
    params = map(lambda p: '{}={}'.format(*p), params)
    url = 'https://bugzilla.mozilla.org/buglist.cgi?' + '&'.join(params) + '&limit=0'
    return url


def generate_html(path='data', output='generated'):
    backlog = get_backlog(path=path)
    managers = backlog['managers']
    owners = backlog['owners']
    teams = backlog['teams']
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('triage_owner.html')
    if not os.path.isdir(output):
        os.makedirs(output)

    people = set(managers.keys()) | set(owners.keys())
    labels = backlog['labels']
    tree = make_all_tree(teams, people)
    to_manager = get_person_to_manager(teams)

    for name in people:
        raw = {}
        cumulate = {}
        comps = []
        team = []
        urls = {}
        if name in managers:
            d = managers[name]
            raw['Global as manager'] = d['raw']
            cumulate['Global as manager'] = d['cumulate']
            comps = ['Global as manager']
            team = tree[name]

        if name in owners:
            d = owners[name]
            cps = set(d['raw'].keys())
            cps.remove('Global')
            cps = list(sorted(cps))
            for c in cps:
                urls[c] = get_url_for_pc(c)
            comps = comps + ['Global as owner'] + cps

            raw.update(d['raw'])
            cumulate.update(d['cumulate'])
            raw['Global as owner'] = raw['Global']
            del raw['Global']
            cumulate['Global as owner'] = cumulate['Global']
            del cumulate['Global']

        if name in to_manager:
            manager_name = to_manager[name]
            manager_team = tree[manager_name]
        else:
            manager_team = []

        html = template.render(name=name,
                               team=team,
                               manager_team=manager_team,
                               manager_name=manager_name,
                               labels=labels,
                               raw=raw,
                               cumulate=cumulate,
                               comps=comps,
                               urls=urls,
                               str=str,
                               jsonify=json.dumps)
        gpath = '{}/{}.html'.format(output, name)
        with open(gpath, 'w') as Out:
            Out.write(html)

    template = env.get_template('index.html')
    html = template.render(names=sorted(people))
    gpath = '{}/index.html'.format(output)
    with open(gpath, 'w') as Out:
        Out.write(html)

    copyfile('static/triage.js', '{}/triage.js'.format(output))
    copyfile('static/triage.css', '{}/triage.css'.format(output))

#make_team_stats()
#generate_html()
