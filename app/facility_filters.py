"""Streamlit 화면에서 사용하는 세부 시설 선택 컴포넌트."""

from collections.abc import Mapping

import streamlit as st


LABELS = {
    "daily_life": "생활시설",
    "healthcare": "의료",
    "transport": "교통",
    "leisure_community": "여가시설",
}


def render_facility_filters(options: Mapping[str, list[str]], *, key_prefix="facilities") -> dict[str, list[str]]:
    """available_facility_types()의 결과를 받아 선택값을 반환합니다.

    화면의 지도·점수·추천에 동일한 반환값을 전달하세요. 선택지가 없는
    항목은 자료 준비 중으로 표시하며, 전체 무선택이면 계산을 중단해야 합니다.
    """
    selected = {}
    st.caption("분석에 포함할 시설을 선택하세요. 선택하지 않은 시설은 점수와 지도에서 제외됩니다.")
    for category, label in LABELS.items():
        values = options.get(category, [])
        if values:
            selected[category] = st.multiselect(
                label, options=values, default=values, key=f"{key_prefix}_{category}",
            )
        else:
            st.caption(f"{label}: 선택 가능한 자료를 준비하고 있습니다.")
            selected[category] = []
    if not any(selected.values()):
        st.warning("분석할 시설을 하나 이상 선택하세요.")
    return selected
