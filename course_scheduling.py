import pandas as pd
from bs4 import BeautifulSoup
import requests
import re
import json
import pandas as pd
import numpy as np
import networkx as nx


def getCourseList():
    url = "https://uspdigital.usp.br/jupiterweb/jupDisciplinaLista?codcg=60&pfxdisval=CGF&tipo=D"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'lxml') # Parse the HTML as a string
    tables = soup.find_all('table') # Grab the first table

    row_list = []
    for table in tables:
      for row in table.find_all('tr'):
          column_list = []
          columns = row.find_all('td')
          for column in columns:
              column_list.append(column.get_text())
          row_list.append(column_list)
    fulltxt = ' '.join(list(itertools.chain(*row_list)))
    return list(set(re.findall('CGF\d{4}', fulltxt)))

def getDependence(course_code):
    url = f'https://uspdigital.usp.br/jupiterweb/listarCursosRequisitos?coddis={course_code}'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'lxml') # Parse the HTML as a string
    tables = soup.find_all('table') # Grab the first table

    row_list = []
    for table in tables:
      for row in table.find_all('tr'):
          column_list = []
          columns = row.find_all('td')
          for column in columns:
              column_list.append(column.get_text())
          row_list.append(column_list)
    fulltxt = ' '.join(list(itertools.chain(*row_list)))
    return list(set(re.findall('CGF\d{4}', fulltxt))-{course_code})

def getCourseInfo(course_code):
    info = {}
    url_course = f"https://uspdigital.usp.br/jupiterweb/obterDisciplina?sgldis={course_code}"
    response_course = requests.get(url_course)
    soup = BeautifulSoup(response_course.text, 'lxml') # Parse the HTML as a string
    tabs = soup.find_all('table')
    row_list = []
    for tab in tabs:
      for row in tab.find_all('tr'):
          column_list = []
          columns = row.find_all('td')
          for column in columns:
              column_list.append(column.get_text())
          row_list.append(column_list)

    fulltxt = ' '.join(list(itertools.chain(*row_list)))

    sdisc = re.search('Disciplina: .+\n', fulltxt).span()
    info['name'] = re.sub(r'Disciplina: (.+)\n', r'\1', fulltxt[sdisc[0]:sdisc[1]])
    scra = re.search('Créditos Aula: \s+\d+', fulltxt).span()
    info['creditos_aula'] = re.sub(r'Créditos Aula: \s+(\d+)', r'\1', fulltxt[scra[0]:scra[1]])
    scrt = re.search('Créditos Trabalho: \s+\d+', fulltxt).span()
    info['creditos_trabalho'] = re.sub(r'Créditos Trabalho: \s+(\d+)', r'\1', fulltxt[scrt[0]:scrt[1]])
    sch = re.search('Carga Horária Total:\s+.+h', fulltxt).span()
    info['carga_horaria'] = re.sub(r'\D', '', fulltxt[sch[0]:sch[1]])
    sdoc = re.search('Docente\(s\) Responsável\(eis\)', fulltxt).span()
    sprr = re.search('Programa Resumido', fulltxt).span()
    info['docentes'] = re.sub(r'Docente\(s\) Responsável\(eis\)\s+(\d+\w+)\s+', r'\1', fulltxt[sdoc[0]:sprr[0]]).strip()
    spr = re.search('Programa\n', fulltxt).span()
    info['programa_resumido'] = re.sub(r'Programa Resumido\s+(\w+)', r'\1', fulltxt[sprr[1]:spr[0]]).strip()
    sava = re.search('Avaliação\n', fulltxt).span()
    info['programa'] = re.sub(r'Programa\s+(\w+)', r'\1', fulltxt[spr[0]:sava[0]]).strip()
    sbbl = re.search('Bibliografia\n', fulltxt).span()
    info['avaliacao'] = re.sub(r'Avaliação\s+(\w+)', r'\1', fulltxt[sava[0]:sbbl[0]]).strip()
    sclk = re.search('Clique', fulltxt).span()
    info['bibliografia'] = re.sub(r'Bibliografia\s+(\w+)', r'\1', fulltxt[sbbl[0]:sclk[0]]).strip()
    info['requisitos'] = getDependence(course_code)
    return info

if __name__=='__main__':
    courses = getCourseList()

    print("Recovered:", len(courses), "courses.")

    dcourses = []
    for c in courses:
        dcourses.append(getCourseInfo(c))
        print("Recovered information from", c)

    print("Saving json of course info:")
    with open('courses.json', 'w') as f:
        json.dump(dcourses, f, indent=True)

    print("Subselecting course information.")
    sdict = []

    for d in dcourses:
        d.pop("programa_resumido")
        d.pop("programa")
        d.pop("avaliacao")
        d.pop("bibliografia")
        d["requisitos"] = ', '.join(d["requisitos"])
        d["docentes"] = re.sub('\s{2,}', ',', d['docentes'])
        sdict.append(d)

    df = pd.DataFrame(sdict)
    print("Saving csv of course info:")
    df.to_csv('courses.csv', index=False)

    print('Build requirement adjacency matrix')
    n = len(courses)
    adj = np.zeros(shape=(n,n))

    for i in df.index:
        req = df.loc[i, 'requisitos'].split(', ')
        for r in req:
            if r in courses:
                j = courses.index(r)
                adj[i, j] = 1

    padj = pd.DataFrame(adj, columns=courses, index=courses)

    edlst = padj.stack().reset_index()
    edlst.columns = ['source', 'target', 'value']
    edlst = edlst[edlst['value'] == 1]

    #https://networkx.org/documentation/stable/reference/generated/networkx.convert_matrix.from_pandas_edgelist.html
    G = nx.from_pandas_edgelist(edlst)

    pos = nx.spring_layout(G)
    nx.draw(G, pos, font_size=16)
    for p in pos:  # raise text positions
        pos[p][1] += 0.07
    nx.draw_networkx_labels(G, pos)

    print("Saving requirements graph:")
    nx.write_graphml_lxml(G, "requisitos.graphml")

