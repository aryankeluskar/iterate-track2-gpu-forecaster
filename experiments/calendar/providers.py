"""Panel providers (fastgpu_daily + gpurentalprices panels of rental_all): display name and own domains."""
P = {
    "lium": ("Lium", ["lium.io"]), "hyperstack": ("Hyperstack", ["hyperstack.cloud"]),
    "verda": ("Verda (DataCrunch)", ["verda.com", "datacrunch.io"]), "gcp": ("Google Cloud", ["cloud.google.com"]),
    "azure": ("Microsoft Azure", ["azure.microsoft.com", "learn.microsoft.com"]), "aws": ("AWS", ["aws.amazon.com"]),
    "lambdalabs": ("Lambda", ["lambda.ai", "lambdalabs.com"]), "coreweave": ("CoreWeave", ["coreweave.com"]),
    "modal": ("Modal", ["modal.com"]), "salad": ("Salad Cloud", ["salad.com"]), "spheron": ("Spheron", ["spheron.network", "spheron.ai"]),
    "tensordock": ("TensorDock", ["tensordock.com"]), "massedcompute": ("Massed Compute", ["massedcompute.com"]),
    "impossiblecloud": ("Impossible Cloud", ["impossiblecloud.com"]), "nebius": ("Nebius", ["nebius.com"]),
    "vultr": ("Vultr", ["vultr.com"]), "daytona": ("Daytona", ["daytona.io"]), "koyeb": ("Koyeb", ["koyeb.com"]),
    "oci": ("Oracle Cloud", ["oracle.com"]), "digitalocean": ("DigitalOcean", ["digitalocean.com"]),
    "paperspace": ("Paperspace", ["paperspace.com"]), "clore": ("Clore.ai", ["clore.ai"]), "ovhcloud": ("OVHcloud", ["ovhcloud.com"]),
    "cerebrium": ("Cerebrium", ["cerebrium.ai"]), "baseten": ("Baseten", ["baseten.co"]), "jarvislabs": ("Jarvislabs", ["jarvislabs.ai"]),
    "crusoe": ("Crusoe", ["crusoe.ai"]), "together": ("Together AI", ["together.ai"]), "replicate": ("Replicate", ["replicate.com"]),
    "fal": ("fal.ai", ["fal.ai"]), "thundercompute": ("Thunder Compute", ["thundercompute.com"]), "gmi": ("GMI Cloud", ["gmicloud.ai"]),
    "latitude": ("Latitude.sh", ["latitude.sh"]), "fireworks": ("Fireworks AI", ["fireworks.ai"]), "scaleway": ("Scaleway", ["scaleway.com"]),
    "primeintellect": ("Prime Intellect", ["primeintellect.ai"]), "deepinfra": ("DeepInfra", ["deepinfra.com"]),
    "quantacloud": ("QuantaCloud", ["quantacloud.net", "quantacloud.ai"]), "northflank": ("Northflank", ["northflank.com"]),
    "tensorwave": ("TensorWave", ["tensorwave.com"]), "cloudrift": ("CloudRift", ["cloudrift.ai"]), "exoscale": ("Exoscale", ["exoscale.com"]),
    "voltagepark": ("Voltage Park", ["voltagepark.com"]), "theta": ("Theta EdgeCloud", ["thetaedgecloud.com", "thetatoken.org"]),
    "runcrate": ("Runcrate", ["runcrate.ai"]), "synteq": ("Synteq", ["synteq.ai"]), "hotaisle": ("Hot Aisle", ["hotaisle.xyz"]),
    "openrelay": ("OpenRelay", ["openrelay.com"]), "cudo": ("Cudo Compute", ["cudocompute.com"]), "novita": ("Novita AI", ["novita.ai"]),
    "sfcompute": ("SF Compute", ["sfcompute.com"]), "linode": ("Akamai Linode", ["linode.com", "akamai.com"]),
    "hyperai": ("HyperAI", ["hyperai.ai"]), "hetzner": ("Hetzner", ["hetzner.com"]), "gpuwerk": ("GPUwerk", ["gpuwerk.com"]),
}

# Live price-tracker / price-comparison sites: never requested, never fetched (their text updates daily).
TRACKERS = ["computeprices.com", "gpuperhour.com", "gpueconomy.com", "priceofcompute.com", "flopper.io", "askgpu.com", "fastgpu.co",
            "gpurentalprices.com", "computestacker.com", "gpubeacon.com", "lowcostgpu.com", "gpusmith.com", "thegpu.ai", "compute.cheap",
            "nexgpu.net", "coloprice.com", "cheapestgpu.com", "gpuprice.in", "getdeploying.com", "cloudgpuhub.com", "gpuaas.com",
            "indiagpu.com", "silicondata.com", "gpus.io", "shadeform.ai", "cloud-gpus.com", "gpucost.org", "computingpower.org",
            "gpulist.ai", "vast.ai", "gpuhunt.com", "cloudgpus.io", "fullstackdeeplearning.com", "computewatch.com", "gpucompare.com",
            "withorb.com", "usagepricing.com", "pricingsaas.com", "computecollege.com", "aiforge.works", "gpu-prices.com", "llm-stats.com"]
