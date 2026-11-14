"""Write data_out/repricing_calendar.jsonl from the hand-read Exa sources (runs/calendar/contents.json + search hits).
One line per announcement (provider x effective date); `changes` lists the GPUs. Quotes are copied from Exa text, not paraphrased.
`published` is Exa's publishedDate of the quoted source (the leak-safe availability date); `usable_from` = published."""
import json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[2]


def ch(gpu, panel_gpus, tier, old, new):
    return dict(gpu=gpu, panel_gpus=panel_gpus, tier=tier, old=old, new=new,
                pct=None if old in (None, 0) or new is None else round(new / old - 1, 4))


def salad(url, eff, published, pub_note, tiers):
    t = json.load(open(ROOT / "runs/calendar/contents.json"))[url]["text"]
    out = []
    for row in re.findall(r"^\| (RTX[^|(]+?) \(\d+ GB\) \|(.+)$", t, re.M):
        name, cells = row[0].strip(), [c.strip() for c in row[1].split("|") if c.strip()]
        for tier, cell in zip(tiers, cells):
            m = re.findall(r"\$([\d.]+)", cell)
            if len(m) >= 2:
                out.append(ch(name, [name], tier, float(m[0]), float(m[1])))
    return out


E = [
    dict(provider="nebius", effective_date="2026-10-01", effective_utc="2026-10-01T00:00Z", published="2026-09-16",
         url="https://longbridge.com/en/topics/100000000903151",
         title="$Nebius(NBIS.US) INCREASE ON-DEMAND GPU RATES EFFECTIVE OCTOBER 1 | Longbridge",
         quote="$Nebius(NBIS.US) INCREASE ON-DEMAND GPU RATES EFFECTIVE OCTOBER 1. H100: $3.85 per GPU-hour -> $4.50 H200: $4.50 per GPU-hour -> $5.40 B200: $7.15 per GPU-hour -> $8.50 B300: $7.85 per GPU-hour -> $9.50",
         quote_states_effective_date=True, source_type="relay of customer notice (social post), corroborated by press",
         also=[dict(url="https://www.thefivenines.com/data-ai/nebius-raises-gpu-prices-20-as-supply-tightens", published="2026-09-16",
                    quote="Nebius said it will raise GPU cloud prices by an average of 20 percent from October 1, covering H100, H200, B200 and B300 chips, with B300 rising from $7.85 to $9.50 per GPU-hour."),
               dict(url="https://www.reuters.com/technology/nebius-hikes-ai-cloud-prices-again-demand-computing-power-soars-2026-09-17/", published="2026-09-17",
                    quote="Cloud provider Nebius (NBIS.O) said on Thursday it will raise pay-as-you-go prices for leasing selected Nvidia chips from October 1"),
               dict(url="https://gpucloudadvisors.com/news/nebius-october-gpu-price-increase/", published="2026-09-28",
                    quote="HGX H100, per GPU hour $3.85 now, $4.50 from October 1 ... HGX B300, per GPU hour $7.85 now, $9.50 from October 1. RTX PRO 6000 stays at $1.80.")],
         changes=[ch("H100", ["H100 SXM 80GB", "H100 80GB"], "on_demand", 3.85, 4.50), ch("H200", ["H200"], "on_demand", 4.50, 5.40),
                  ch("B200", ["B200"], "on_demand", 7.15, 8.50), ch("B300", ["B300"], "on_demand", 7.85, 9.50)],
         confidence="A", edited_after_published=False, edit_note="", announced_before_effective=True),
    dict(provider="jarvislabs", effective_date="2026-10-05", effective_utc="2026-10-04T18:30Z", published="2026-09-24",
         url="https://jarvislabs.ai/updates/gpu-pricing-october-2026", title="New GPU rates from October 5, 2026 | Jarvislabs Updates",
         quote="From October 5, 2026 at 00:00 IST, new rates apply to NVIDIA H200, H100 and RTX PRO 6000 GPUs. ... NVIDIA H200 SXM | $3.99/hr | $4.59/hr | NVIDIA H100 SXM | $2.69/hr | $3.49/hr | NVIDIA RTX PRO 6000 | $1.89/hr | $2.19/hr",
         quote_states_effective_date=True, source_type="provider changelog", also=[],
         changes=[ch("H200", ["H200"], "on_demand", 3.99, 4.59), ch("H100 SXM", ["H100 SXM 80GB"], "on_demand", 2.69, 3.49),
                  ch("RTX PRO 6000", ["RTX PRO 6000"], "on_demand", 1.89, 2.19)],
         confidence="A", edited_after_published=False, edit_note="Exa text matches the search-time highlight; no dates after publication other than the effective date.",
         announced_before_effective=True),
    dict(provider="fireworks", effective_date="2026-09-01", effective_utc="2026-09-01T00:00Z", published="2026-08-13",
         url="https://modelswar.com/change/fireworks-h100-80gb-gpu-price-increases-effective-sep-1-26509/",
         title="Fireworks: H100 80GB GPU price increases effective Sep 1 — ModelsWar",
         quote="GPU Type: H100 80 GB GPU + Price ($) per hour - upto Aug 31: $7.00 + Price ($) per hour - from Sep 1: $8.00",
         quote_states_effective_date=True, source_type="third-party change detector quoting fireworks.ai/pricing (dated per-change page, not a live price list)",
         also=[dict(url="https://modelswar.com/change/fireworks-b200-180gb-gpu-price-increases-effective-sep-1-26506/", published="2026-08-13",
                    quote="Price ($) per hour - upto Aug 31: $10.00 + Price ($) per hour - from Sep 1: $13.00"),
               dict(url="https://modelswar.com/change/fireworks-h200-141gb-gpu-price-increases-effective-sep-1-26510/", published="2026-08-13",
                    quote="H200 141 GB GPU ... upto Aug 31: $7.00 ... from Sep 1: $8.00")],
         changes=[ch("H100 80GB", ["H100 80GB"], "on_demand_deployment", 7.00, 8.00), ch("H200", ["H200"], "on_demand_deployment", 7.00, 8.00),
                  ch("B200", ["B200"], "on_demand_deployment", 10.00, 13.00)],
         confidence="B", edited_after_published=True,
         edit_note="Page footer reads 'Published 3 months ago' (rendered after 2026-11-06); change text itself is dated 13 Aug.",
         announced_before_effective=True),
    dict(provider="salad", effective_date="2026-09-12", effective_utc="2026-09-12T00:00Z", published="2026-09-01",
         url="https://blog.salad.com/saladcloud-price-changes-september-2026/", title="Upcoming SaladCloud Price Changes: September 12, 2026",
         quote="These changes take effect Saturday, September 12, 2026 at 00:00 UTC ... At High Priority, the RTX 5090 moves from $0.450 to $0.500 and the RTX 4090 from $0.300 to $0.330.",
         quote_states_effective_date=True, source_type="provider blog", also=[],
         changes=salad("https://blog.salad.com/saladcloud-price-changes-september-2026/", "2026-09-12", "2026-09-01", "", ["high", "medium", "low", "lowest"]),
         confidence="A", edited_after_published=False, edit_note="", announced_before_effective=True),
    dict(provider="salad", effective_date="2026-11-01", effective_utc="2026-11-01T00:00Z", published="2026-11-01",
         url="https://blog.salad.com/saladcloud-price-changes-november-2026", title="Upcoming SaladCloud Price Changes: November 1, 2026",
         quote="These changes take effect Sunday, November 1, 2026 at 00:00 UTC ... High Priority prices are increasing on 21 GPU classes, by 10% to 20% on most of them.",
         quote_states_effective_date=True, source_type="provider blog", also=[],
         changes=salad("https://blog.salad.com/saladcloud-price-changes-november-2026", "2026-11-01", "2026-11-01", "", ["high", "medium", "low"]),
         confidence="A", edited_after_published=False,
         edit_note="Exa publishedDate 2026-11-01; the post's own byline reads Mon Oct 26 2026 (5 days' notice). Calendar uses the later Exa date.",
         announced_before_effective=False),
    dict(provider="lambdalabs", effective_date="2026-11-16", effective_utc="2026-11-16T00:00Z", published="2026-11-06",
         url="https://gpujournal.ai/story/lambda-announced-rises-nov-16",
         title="Lambda announces GPU price rises of about 15% — B200, H100 and A100 80GB, from Nov 16 | GPUJournal",
         quote="'These prices take effect November 16, 2026, at 00:00 UTC. Until then, log in to your Lambda Cloud account to see current pricing.' The printed Nov 16 rates: HGX B200 $7.69 an hour (from the $6.69 last verified on Nov 5, +14.9%), HGX H100 $4.59 (from $3.99, +15.0%), HGX A100 80GB $3.19 (from $2.79, +14.3%), and HGX A100 40GB unchanged at $1.99.",
         quote_states_effective_date=True, source_type="news site quoting Lambda's pricing page (read Nov 6)", also=[],
         changes=[ch("B200", ["B200"], "on_demand", 6.69, 7.69), ch("H100 SXM", ["H100 SXM 80GB"], "on_demand", 3.99, 4.59),
                  ch("A100 80GB", ["A100 SXM 80GB", "A100 80GB"], "on_demand", 2.79, 3.19), ch("A100 40GB", ["A100 40GB"], "on_demand", 1.99, 1.99)],
         confidence="B", edited_after_published=False,
         edit_note="Published on the cutoff day; old prices are the site's last verified values (Nov 5), not stated by Lambda. Lambda's own page was not opened (live pricing page).",
         announced_before_effective=True),
    dict(provider="aws", effective_date="2026-10-07", effective_utc="2026-10-07T00:00Z", published="2026-09-30",
         url="https://cryptobriefing.com/aws-gpu-capacity-block-price-increase/",
         title="AWS reportedly lifts GPU capacity prices again, with a 15% hike flagged for October 7",
         quote="A post on X claims AWS is lifting reserved compute prices for a fourth quarter, with a 15% increase set to begin October 7.",
         quote_states_effective_date=True, source_type="press relaying a social post; AWS rate page quoted next day",
         also=[dict(url="https://fourweekmba.com/ai-aws-ec2-capacity-block-rates-october-2026/", published="2026-10-01",
                    quote="P6-B300 at $16.146, P6-B200 at $14.208, P5en at $7.895, P5e at $6.866, and P5 at $5.970, P4de at $2.546 and P4d at $1.696. ... all other Capacity Block prices — and prices on fixed models including On-Demand and Savings Plans — remain unchanged.")],
         changes=[ch("B300", ["B300"], "capacity_block", None, 16.146), ch("B200", ["B200"], "capacity_block", None, 14.208),
                  ch("H200 (P5en)", ["H200"], "capacity_block", None, 7.895), ch("H100 (P5)", ["H100 SXM 80GB"], "capacity_block", None, 5.970),
                  ch("A100 80GB (P4de)", ["A100 80GB", "A100 SXM 80GB"], "capacity_block", None, 2.546), ch("A100 40GB (P4d)", ["A100 40GB"], "capacity_block", None, 1.696)],
         confidence="B", edited_after_published=True,
         edit_note="fourweekmba carries a 'Correction, 1 October 2026' inside the text (edited after first posting, same day). Tier is Capacity Blocks; on-demand stated unchanged, so no panel effect expected.",
         announced_before_effective=True),
    dict(provider="digitalocean", effective_date="2026-08-01", effective_utc="2026-08-01T00:00Z", published="2026-08-02",
         url="https://theweightedaverage.com/notes/2026-08-02-digitalocean-gpu-price-hike/", title="DigitalOcean raises H100 rental prices 30% • The Weighted Average",
         quote="DigitalOcean raised on-demand H100 GPU Droplet pricing 30%, from $3.39 to $4.41 per GPU-hour, while H200 pricing climbed from $3.44 to $4.47 on August 1.",
         quote_states_effective_date=True, source_type="press, reported after the change", also=[],
         changes=[ch("H100", ["H100 SXM 80GB", "H100 80GB"], "on_demand", 3.39, 4.41), ch("H200", ["H200"], "on_demand", 3.44, 4.47)],
         confidence="C", edited_after_published=False, edit_note="Published the day after the effective date: not an advance announcement.",
         announced_before_effective=False),
]

if __name__ == "__main__":
    out = ROOT / "data_out" / "repricing_calendar.jsonl"
    with open(out, "w") as f:
        for e in sorted(E, key=lambda e: (e["effective_date"], e["provider"])):
            e["lead_days"] = (__import__("datetime").date.fromisoformat(e["effective_date"]) - __import__("datetime").date.fromisoformat(e["published"])).days
            e["usable_from"] = e["published"]
            f.write(json.dumps(e) + "\n")
    print(len(E), "entries ->", out, "| changes:", sum(len(e["changes"]) for e in E))
