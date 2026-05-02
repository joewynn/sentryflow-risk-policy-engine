"""
Graph analytics for synthetic identity fraud detection.

Synthetic identity rings are statistically normal in isolation (pass XGBoost screening).
What betrays them: shared infrastructure (same email, address, card, device).

This module builds a transaction-transaction graph via shared identity attributes,
then computes scalar graph features (degree, connected component size) that feed
into the tabular ML pipeline.

Reference: Revisiting Graph-Based Fraud Detection (arXiv 2312.06441)
"""
import networkx as nx
import pandas as pd
from typing import Tuple


def build_shared_identity_graph(df: pd.DataFrame) -> nx.Graph:
    """
    Construct transaction-transaction graph via shared identity attributes.

    Nodes: transaction IDs
    Edges: transactions sharing any identity attribute (card1, P_emaildomain, addr1, addr2)
    Edge metadata: 'via' attribute indicates which attribute was shared

    Args:
        df: DataFrame with columns TransactionID, card1, P_emaildomain, addr1, addr2

    Returns:
        NetworkX undirected graph (not bipartite — reduced to transactions only)
    """
    G = nx.Graph()

    # Add all transaction nodes
    if "TransactionID" in df.columns:
        G.add_nodes_from(df["TransactionID"].tolist())
    else:
        G.add_nodes_from(range(len(df)))

    # Identity columns to use for grouping (order matters — longer identifiers first)
    identity_cols = ["card1", "P_emaildomain", "addr1", "addr2"]

    for col in identity_cols:
        if col not in df.columns:
            continue

        # Group by attribute value
        for attr_value, group_df in df.dropna(subset=[col]).groupby(col, observed=True):
            tx_list = group_df.index.tolist() if "TransactionID" not in group_df.columns else group_df["TransactionID"].tolist()

            # Connect all pairs within group (but cap at 50 edges per attribute to avoid explosion)
            if len(tx_list) > 1:
                for i in range(len(tx_list)):
                    for j in range(i + 1, min(i + 50, len(tx_list))):
                        G.add_edge(tx_list[i], tx_list[j], via=col)

    return G


def extract_graph_features(G: nx.Graph, df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract scalar graph features for each transaction.

    Features:
    - graph_degree: number of neighbors (shared-attribute connections)
    - graph_cc_size: size of connected component (fraud ring size)
    - graph_shared_email_cnt: neighbors via email domain (email ring affinity)
    - graph_shared_addr_cnt: neighbors via address (address ring affinity)

    Key insight: Legitimate users in small components (1-5), SIF rings large (50-500).

    Args:
        G: NetworkX graph from build_shared_identity_graph()
        df: Original DataFrame (to align with transaction index)

    Returns:
        DataFrame with graph features, indexed by TransactionID or integer index
    """
    # Precompute all connected components once (O(N) instead of O(N²))
    cc_mapping = {}
    for component in nx.connected_components(G):
        cc_size = len(component)
        for node in component:
            cc_mapping[node] = cc_size

    rows = []
    tx_ids = df.index.tolist() if "TransactionID" not in df.columns else df["TransactionID"].tolist()

    for tx_id in tx_ids:
        if tx_id in G:
            # Transaction has at least one shared attribute connection
            neighbors = list(G.neighbors(tx_id))
            cc_size = cc_mapping.get(tx_id, 1)

            # Count neighbors by shared attribute type
            email_cnt = 0
            addr_cnt = 0
            for neighbor in neighbors:
                edge_data = G[tx_id][neighbor]
                via = edge_data.get("via", "")
                if via == "P_emaildomain":
                    email_cnt += 1
                elif via in ("addr1", "addr2"):
                    addr_cnt += 1

            rows.append(
                {
                    "graph_degree": G.degree(tx_id),
                    "graph_cc_size": cc_size,
                    "graph_shared_email_cnt": email_cnt,
                    "graph_shared_addr_cnt": addr_cnt,
                }
            )
        else:
            # Isolated transaction (no shared attributes)
            rows.append(
                {
                    "graph_degree": 0,
                    "graph_cc_size": 1,
                    "graph_shared_email_cnt": 0,
                    "graph_shared_addr_cnt": 0,
                }
            )

    # Create DataFrame and align with input
    features_df = pd.DataFrame(rows)

    # Handle both integer index (from backtest_flow) and TransactionID column
    if "TransactionID" in df.columns:
        features_df.index = df["TransactionID"].values
        features_df.index.name = "TransactionID"
    else:
        features_df.index = df.index

    return features_df
