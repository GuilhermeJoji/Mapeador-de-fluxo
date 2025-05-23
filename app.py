# -*- coding: utf-8 -*-
"""
@author: guijoji
"""

import streamlit as st
import uuid
import xml.etree.ElementTree as ET
from xml.dom import minidom

def id_gen():
    return "id_" + str(uuid.uuid4())[:8]

def ler_txt_para_passos(conteudo_txt):
    passos = []
    for linha in conteudo_txt.splitlines():
        linha = linha.strip()
        if linha.startswith("PASSO:"):
            partes = linha.split("|")
            nome = partes[0].replace("PASSO:", "").strip()
            executor = partes[1].replace("EXECUTOR:", "").strip()
            passos.append({"nome": nome, "executor": executor, "tipo": "task"})
        elif linha.startswith("DECISAO:"):
            partes = linha.split("|")
            nome = partes[0].replace("DECISAO:", "").strip()
            executor = partes[1].replace("EXECUTOR:", "").strip()
            condicoes = []
            for parte in partes[2:]:
                if "->" in parte:
                    cond, prox = parte.split("->")
                    condicoes.append({"condicao": cond.strip(), "proximo": prox.strip()})
            passos.append({"nome": nome, "executor": executor, "tipo": "gateway", "condicoes": condicoes})
    return passos

def gerar_bpmn_com_lanes(passos):
    NS = {
        "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
        "dc": "http://www.omg.org/spec/DD/20100524/DC",
        "di": "http://www.omg.org/spec/DD/20100524/DI",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance"
    }
    ET.register_namespace("", NS["bpmn"])
    for prefix, uri in NS.items():
        ET.register_namespace(prefix, uri)

    definitions = ET.Element("definitions", {
        "xmlns": NS["bpmn"],
        "xmlns:xsi": NS["xsi"],
        "xmlns:bpmndi": NS["bpmndi"],
        "xmlns:dc": NS["dc"],
        "xmlns:di": NS["di"],
        "id": "Definitions_1",
        "targetNamespace": "http://bpmn.io/schema/bpmn"
    })

    process = ET.SubElement(definitions, "process", {
        "id": "Process_1",
        "isExecutable": "false"
    })

    executores = list({p["executor"] for p in passos})
    lanes = {}
    laneSet = ET.SubElement(process, "laneSet", {"id": "LaneSet_1"})
    for idx, exec in enumerate(executores):
        lane_id = f"Lane_{idx}"
        lane = ET.SubElement(laneSet, "lane", {"id": lane_id, "name": exec})
        lanes[exec] = lane

    bpmndiagram = ET.SubElement(definitions, "bpmndi:BPMNDiagram", {"id": "BPMNDiagram_1"})
    plane = ET.SubElement(bpmndiagram, "bpmndi:BPMNPlane", {"id": "BPMNPlane_1", "bpmnElement": "Process_1"})

    element_ids = {}
    element_positions = {}
    sequence_flows = []

    spacing_x = 200
    spacing_y = 150
    y_map = {executor: i * spacing_y + 100 for i, executor in enumerate(executores)}

    x_pos = 100
    start_id = id_gen()
    ET.SubElement(process, "startEvent", {"id": start_id, "name": "Início"})
    element_ids["Início"] = start_id
    element_positions[start_id] = (x_pos, 50)
    x_pos += spacing_x
    prev_id = start_id

    for passo in passos:
        eid = id_gen()
        element_ids[passo["nome"]] = eid
        y = y_map[passo["executor"]]
        element_positions[eid] = (x_pos, y)

        if passo["tipo"] == "task":
            ET.SubElement(process, "task", {"id": eid, "name": passo["nome"]})
        elif passo["tipo"] == "gateway":
            ET.SubElement(process, "exclusiveGateway", {"id": eid, "name": passo["nome"]})

        ET.SubElement(lanes[passo["executor"]], "flowNodeRef").text = eid
        sequence_flows.append((prev_id, eid, ""))
        prev_id = eid
        x_pos += spacing_x

    end_id = id_gen()
    ET.SubElement(process, "endEvent", {"id": end_id, "name": "Fim"})
    element_ids["Fim"] = end_id
    element_positions[end_id] = (x_pos, 50)
    sequence_flows.append((prev_id, end_id, ""))

    for passo in passos:
        if passo["tipo"] == "gateway":
            gateway_id = element_ids[passo["nome"]]
            for cond in passo["condicoes"]:
                destino = cond["proximo"]
                cond_text = cond["condicao"]
                if destino not in element_ids:
                    eid = id_gen()
                    element_ids[destino] = eid
                    y = y_map[passo["executor"]] + 80
                    element_positions[eid] = (x_pos, y)
                    ET.SubElement(process, "task", {"id": eid, "name": destino})
                    ET.SubElement(lanes[passo["executor"]], "flowNodeRef").text = eid
                sequence_flows.append((gateway_id, element_ids[destino], cond_text))

    for i, (src, tgt, nome) in enumerate(sequence_flows):
        fid = f"Flow_{i+1}"
        flow = ET.SubElement(process, "sequenceFlow", {
            "id": fid,
            "sourceRef": src,
            "targetRef": tgt
        })
        if nome:
            cond = ET.SubElement(flow, "conditionExpression", {"xsi:type": "tFormalExpression"})
            cond.text = nome

        edge = ET.SubElement(plane, "bpmndi:BPMNEdge", {
            "id": f"{fid}_di",
            "bpmnElement": fid
        })
        for eid in [src, tgt]:
            x, y = element_positions[eid]
            ET.SubElement(edge, "di:waypoint", {
                "x": str(x + 50),
                "y": str(y + 40)
            })

    for nome, eid in element_ids.items():
        x, y = element_positions[eid]
        shape = ET.SubElement(plane, "bpmndi:BPMNShape", {
            "id": f"{eid}_di",
            "bpmnElement": eid
        })
        ET.SubElement(shape, "dc:Bounds", {
            "x": str(x), "y": str(y),
            "width": "100", "height": "80"
        })

    xmlstr = minidom.parseString(ET.tostring(definitions)).toprettyxml(indent="   ")
    return xmlstr

# Streamlit UI
st.set_page_config(page_title="Mapeador de Fluxo BPMN By Guilherme Joji", layout="centered")
st.title("Mapeador de Fluxo BPMN com Lanes e Setas - By Guilherme Joji")

st.markdown("""
## 📝 Como usar este app

1. **Transcreva o áudio ou vídeo em um `.txt`.**  
   Ferramenta recomendada: link

2. **Padronize a entrevista em formato de fluxo.**
   Ferramenta recomendada: este Chat com o GPT personalizado.

3. **Insira o arquivo `.txt` da etapa '2)' abaixo para gerar o BPMN.**

""")

uploaded_file = st.file_uploader("📄 Faça upload do arquivo .txt com o processo LEMBRE-SE DE USAR O CHAT PARA PADRONIZAR O FLUXO", type="txt")

if uploaded_file:
    conteudo = uploaded_file.read().decode("utf-8")
    passos = ler_txt_para_passos(conteudo)
    xml_output = gerar_bpmn_com_lanes(passos)

    st.success("✅ Diagrama BPMN gerado com sucesso!")
    st.download_button("📥 Baixar BPMN", xml_output, file_name="processo_modelado.bpmn")
