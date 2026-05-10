##

<h1 align="center">Beyond RGB: Spectral-Spatial Prompting for enhanced Remote Sensing Visual Question Answering</h1>

<div align="center">
<a href="https://orcid.org/0009-0008-6391-1625">Sourabh Barala</a>,
<a href="https://orcid.org/0009-0000-8111-8489">Sumedha Basu</a>,
<a href="https://orcid.org/0000-0001-5797-7654">Kuldeep Ramchandra Kurte</a>
<br>
sourab.barala@research.iiit.ac.in,
sumedha.basu@research.iiit.ac.in,
kuldeep.kurte@iiit.ac.in
<br>

</div>

<h3 align="center">Abstract</h3>

<p align="justify">
Remote Sensing Visual Question Answering (RSVQA) is an emerging natural language interface for querying Earth Observation (EO) information. Although recent Vision-Language Models (VLMs) have shown promising performance, most of the existing RSVQA approaches rely primarily on RGB (visible) imagery and task-specific fine-tuning. This limits the use of multispectral information beyond the visible spectrum and introduces significant computational overhead. Furthermore, the effectiveness of fine-tuning in improving RSVQA performance across diverse sensors and question types remains largely unexplored. In this work, we propose a prompting-based RSVQA framework that explicitly incorporates spectral-spatial descriptors without relying on extensive model fine-tuning. Multispectral information derived from spectral indices is converted into structured textual metadata and injected as contextual prompts into a VLM, which jointly processes the question and the provided context, to generate answers. The proposed framework is evaluated on multi-sensor remote sensing imagery across seven evaluation dimensions. Experimental results comparing a general-purpose VLM and its remote-sensing-fine-tuned variant, both with and without contextual prompting, show that spatially explicit prompting consistently improves performance across most tasks. Notably, the general-purpose VLM with spectral-spatial context outperforms the fine-tuned model in the majority of evaluation settings, highlighting the limitations of task-specific fine-tuning and demonstrating the effectiveness of structured prompting for scalable and robust RSVQA.
</p>
<br>
