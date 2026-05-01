import json

data = json.load(open('juzgados_nacional.json', encoding='utf-8'))
con_mag = [j for j in data if j.get('magistrado')]
con_pjn = [j for j in data if j.get('dictadas_def', 0) > 0]

print(f'Total juzgados:        {len(data)}')
print(f'Con magistrado:        {len(con_mag)}')
print(f'Con dictadas_def real: {len(con_pjn)}')

if con_pjn:
    print('\n--- Ejemplo con datos PJN completos ---')
    j = con_pjn[0]
    print(f'  Juzgado:           {j["juzgado"]}')
    print(f'  Jurisdiccion:      {j["jurisdiccion"]}')
    print(f'  Pendientes inicio: {j["pendientes_inicio"]}')
    print(f'  Dictadas def:      {j["dictadas_def"]}')
    print(f'  Pendientes cierre: {j["pendientes_cierre"]}')
    print(f'  Clearance Rate:    {j["clearance_rate"]}%')
    print(f'  IRA:               {j["ira_semaforo"]} {j["ira_score"]}')