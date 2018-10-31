# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json


def get_ranks(persons, managers):
    # rank 0: people who aren't manager
    # rank N + 1: managers who manage people at most rank N people
    managers = {m: set(t) for m, t in managers.items()}
    ranked = set(persons.keys()) - set(managers.keys())
    res = [ranked]
    while managers:
        _ranked = set()
        for manager, team in managers.items():
            team -= ranked
            if not team:
                _ranked.add(manager)
        for r in _ranked:
            del managers[r]
        res.append(_ranked)
        ranked = _ranked

    return res


def get_teams(path='data'):
    path = '{}/people.json'.format(path)
    with open(path, 'r') as In:
        data = json.load(In)

    persons = {}
    mails = {}
    managers = {}

    for person in data:
        name = person['cn']
        mail = person['bugzillaEmail']
        if not mail:
            mail = person['mail']
        mails[name] = mail
        persons[mail] = name
        manager = person.get('manager', {})
        manager = manager.get('cn', '') if manager else None
        if manager:
            if manager not in managers:
                managers[manager] = [name]
            else:
                managers[manager].append(name)

    # replace names by bugzilla emails
    new_m = {}
    for manager, team in managers.items():
        new_m[mails[manager]] = [mails[p] for p in team]
    managers = new_m

    ranks = get_ranks(persons, managers)

    return {'persons': persons,
            'mails': mails,
            'managers': managers,
            'ranks': ranks}
