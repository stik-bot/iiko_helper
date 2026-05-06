from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://iiko.ispringlearn.ru"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)


@dataclass(slots=True)
class CourseContext:
    track_title: str
    track_id: int
    course_title: str
    course_id: int
    course_uuid: str
    course_url: str


class ISpringClient:
    def __init__(self, login: str, password: str) -> None:
        self.login = login
        self.password = password
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.csrf_token = ""

    def login_user(self) -> None:
        self.session.get(f"{BASE_URL}/login", timeout=30)
        response = self.session.post(
            f"{BASE_URL}/login",
            data={
                "login": self.login,
                "password": self.password,
                "remember": "1",
                "redirect_url": "",
                "authentication_code": "",
            },
            allow_redirects=True,
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Login failed with status {response.status_code}")
        self.csrf_token = self._extract_csrf(response.text)

    def get_assigned_tracks(self) -> list[dict[str, Any]]:
        response = self._api_get("/api/user_portal/courses", referer=f"{BASE_URL}/courses")
        payload = response.json()
        return payload.get("required", [])

    def get_track_details(self, track_id: int) -> dict[str, Any]:
        response = self._api_get(
            f"/api/content/learning-track/{track_id}",
            referer=f"{BASE_URL}/app/user-portal/learning-track/{track_id}",
        )
        return response.json()

    def get_course_modules(self, course_id: int) -> dict[str, Any]:
        course_page = self.session.get(f"{BASE_URL}/content/info/{course_id}", timeout=30)
        component = self._course_component(course_page.text)
        if component is None:
            return {"props": None, "course_uuid": "", "modules": {"singleModules": []}}
        props = json.loads(component["data-props"])
        modules_url = props["contentProps"]["api"]["getCourseContentUrl"]
        course_uuid = props["contentProps"]["lpContentItemUId"]
        modules_response = self.session.get(urljoin(BASE_URL, modules_url), timeout=30)
        modules = modules_response.json()["data"]
        return {"props": props, "course_uuid": course_uuid, "modules": modules}

    def get_module_item_info(self, module_id: str, course_id: int) -> dict[str, Any]:
        response = self.session.post(
            f"{BASE_URL}/content/get_info",
            headers=self._form_headers(referer=f"{BASE_URL}/content/info/{course_id}"),
            data={"item_id": module_id, "learning_path_id": str(course_id)},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_view_options(self, content_key: str, course_id: int) -> dict[str, Any]:
        response = self.session.post(
            f"{BASE_URL}/view_content_item_ajax",
            headers=self._form_headers(referer=f"{BASE_URL}/content/info/{course_id}"),
            data={"vc_cik": content_key, "vc_lpid": str(course_id)},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _course_component(html: str):
        soup = BeautifulSoup(html, "html.parser")
        component = soup.find(id="courseInfoComponent") or soup.find(id="catalogCourseInfoComponent")
        return component

    @staticmethod
    def _extract_csrf(html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        meta = soup.find("meta", {"name": "csrf-token"})
        if meta is None:
            raise RuntimeError("CSRF token not found.")
        return meta.get("content", "")

    def _api_get(self, path: str, referer: str) -> requests.Response:
        response = self.session.get(
            urljoin(BASE_URL, path),
            headers=self._json_headers(referer=referer),
            timeout=30,
        )
        response.raise_for_status()
        return response

    def _json_headers(self, referer: str) -> dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "X-Csrf-Token": self.csrf_token,
            "X-Requested-With": "FetchApiRequest",
            "Referer": referer,
            "Origin": BASE_URL,
        }

    def _form_headers(self, referer: str) -> dict[str, str]:
        return {
            "X-Csrf-Token": self.csrf_token,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": referer,
            "Origin": BASE_URL,
        }


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def collect_text_nodes(node: Any) -> str:
    if isinstance(node, dict):
        parts: list[str] = []
        is_text_leaf = (
            "t" in node
            and isinstance(node["t"], str)
            and "c" not in node
            and "v" not in node
            and "B" not in node
            and "o" not in node
        )
        if is_text_leaf:
            parts.append(node["t"])
        for key, value in node.items():
            if key == "t":
                continue
            parts.append(collect_text_nodes(value))
        return "".join(parts)
    if isinstance(node, list):
        return "".join(collect_text_nodes(item) for item in node)
    return ""


def parse_longread_text(json_payload: dict[str, Any]) -> str:
    raw_text = collect_text_nodes(json_payload.get("content", {}))
    cleaned = normalize_spaces(raw_text)
    return cleaned


def build_keywords(*parts: str) -> list[str]:
    tokens: list[str] = []
    for part in parts:
        for token in re.findall(r"[a-zA-Zа-яА-Я0-9_+-]{3,}", part.lower()):
            if token not in tokens:
                tokens.append(token)
    return tokens[:60]


def scrape_longread_content(client: ISpringClient, item_info: dict[str, Any], course_id: int) -> tuple[str, str]:
    view_options = client.get_view_options(item_info["key"], course_id)
    content_options = view_options["view_content_options"]
    view_url = content_options["view_url"]
    base_url = view_url.rsplit("/", 1)[0] + "/"
    data_url = urljoin(base_url, "data-1.json")
    response = client.session.get(data_url, timeout=30)
    response.raise_for_status()
    payload = response.json()
    return parse_longread_text(payload), view_url


def build_entry(
    *,
    context: CourseContext,
    module_title: str,
    module_type: str,
    text_content: str,
    view_url: str,
) -> dict[str, Any]:
    summary = (
        f"Материал сертификации iiko из iSpring Learn. "
        f"Траектория: {context.track_title}. Курс: {context.course_title}. "
        f"Модуль: {module_title}. Тип: {module_type}."
    )
    return {
        "title": module_title,
        "category": "certification",
        "url": view_url,
        "summary": summary,
        "keywords": build_keywords(context.track_title, context.course_title, module_title, module_type),
        "steps": [],
        "answer": "",
        "content": text_content,
    }


def scrape_certification_materials(login: str, password: str) -> list[dict[str, Any]]:
    client = ISpringClient(login=login, password=password)
    client.login_user()

    entries: list[dict[str, Any]] = []
    tracks = client.get_assigned_tracks()

    for track in tracks:
        track_details = client.get_track_details(int(track["id"]))
        for stage in track_details.get("stages", []):
            for course in stage.get("courses", []):
                course_data = client.get_course_modules(int(course["id"]))
                context = CourseContext(
                    track_title=str(track["title"]),
                    track_id=int(track["id"]),
                    course_title=str(course["title"]),
                    course_id=int(course["id"]),
                    course_uuid=str(course_data["course_uuid"]),
                    course_url=f"{BASE_URL}/content/info/{course['id']}",
                )

                single_modules = course_data["modules"].get("singleModules", [])
                for module in single_modules:
                    item_info = client.get_module_item_info(str(module["id"]), context.course_id)
                    module_type = str(item_info.get("type", "unknown"))
                    module_title = str(item_info.get("title", module.get("title", "")))

                    if module_type == "longread":
                        try:
                            content_text, view_url = scrape_longread_content(client, item_info, context.course_id)
                        except Exception:
                            content_text = ""
                            view_url = urljoin(BASE_URL, str(item_info.get("view_content_url", context.course_url)))
                    else:
                        content_text = (
                            f"Тестовый модуль сертификации. "
                            f"Траектория: {context.track_title}. "
                            f"Курс: {context.course_title}. "
                            f"Название теста: {module_title}."
                        )
                        view_url = urljoin(BASE_URL, str(item_info.get("view_content_url", context.course_url)))

                    entries.append(
                        build_entry(
                            context=context,
                            module_title=module_title,
                            module_type=module_type,
                            text_content=content_text,
                            view_url=view_url,
                        )
                    )

    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync certification materials from iiko iSpring Learn.")
    parser.add_argument("--login", default=os.getenv("ISPRING_LOGIN", "").strip())
    parser.add_argument("--password", default=os.getenv("ISPRING_PASSWORD", "").strip())
    parser.add_argument(
        "--output",
        default="knowledge/ispring_certification.json",
        help="Where to write the generated knowledge JSON.",
    )
    args = parser.parse_args()

    if not args.login or not args.password:
        raise SystemExit("ISPRING_LOGIN and ISPRING_PASSWORD are required.")

    entries = scrape_certification_materials(args.login, args.password)
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(entries)} entries to {output_path}")


if __name__ == "__main__":
    main()
