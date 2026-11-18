import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MEDIA_DIR", "/tmp/tl_test_media")
from app.services import demo
from app.services.matching import MatchConfig, TrackInfo, cluster


def test_demo_scenario_is_recovered_by_the_matcher():
    scenes = demo.generate_scenes()
    infos, truth = [], []
    for ei, sc in enumerate(scenes):
        cam = demo.CAMERAS[sc["camera"]]
        lat, lng = sc["override"] if sc["override"] else (cam["lat"], cam["lng"])
        for o in sc["objects"]:
            infos.append(TrackInfo(len(infos), ei, sc["camera"], o["cls"], o["group"], sc["time"], sc["time"], lat, lng, o["emb"]))
            truth.append(o["identity"])
    clusters, s = cluster(infos, MatchConfig())
    found = sorted(sorted(truth[i] for i in c) for c in clusters)
    print("clusters (by true identity):", found)
    assert sorted(found) == sorted([["A"] * 4, ["B"] * 2, ["V1"] * 2, ["V2"]])


if __name__ == "__main__":
    test_demo_scenario_is_recovered_by_the_matcher(); print("ALL OK")
