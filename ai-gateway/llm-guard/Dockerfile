# ABOUTME: Derived llm-guard-api image: laiyer/llm-guard-api:0.3.16 by digest plus spaCy's zh_core_web_sm and spacy-pkuseg.
# ABOUTME: Anonymize/Sensitive load an en+zh analyzer; with zh baked in, spaCy never pip-installs on the read-only pod.
#   docker build -t us-west1-docker.pkg.dev/kk-community-projects/burritbot/llm-guard-api:0.3.16-burritbot.1 ai-gateway/llm-guard
#
# llm_guard 0.3.16 builds the Presidio analyzer for ["en", "zh"] whatever the
# scanner params say (fixed upstream in ba489b0, never released), and downloads
# any <lang>_core_web_sm it cannot find. The base ships only en_core_web_sm.
# Everything else (uid 1000, HOME /home/user, PYTHONPATH, entrypoint.sh) is the
# base's; the Deployment's checks in tests/test_llm_guard_api_image.py hold for it.
FROM laiyer/llm-guard-api:0.3.16@sha256:bea3efb1220ad18149b73de625c55e6d835bf8b45023a089a3762012a86550ba

COPY --chown=user:user requirements.txt /home/user/zh-requirements.txt
# Into the user site /home/user/.local, beside the base's packages. Each wheel is
# hash-pinned and pip resolves nothing: the dependencies come from the base.
RUN pip install --no-cache-dir --no-deps --require-hashes --user -r /home/user/zh-requirements.txt

# Fail the build, not the pod, if the model or its pkuseg tokenizer does not load.
RUN python -c "import spacy, spacy.util; assert spacy.util.is_package('zh_core_web_sm'); spacy.load('zh_core_web_sm')"
