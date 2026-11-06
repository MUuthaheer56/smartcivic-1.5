from app.routing.osrm import get_distance_matrix

def optimize_worker_sequence(start_lat: float, start_lng: float, tasks: list) -> list:
    """
    Optimizes the sequencing of tasks for a worker starting from a GPS point.
    Uses OSRM travel time matrix to solve the TSP sequence using Nearest-Neighbor heuristic.
    """
    if not tasks:
        return []
    if len(tasks) == 1:
        return tasks

    # 1. Compile coordinate list: starting point + all task locations
    coords = [(start_lat, start_lng)]
    for t in tasks:
        loc = t.get("location", {})
        coords.append((loc.get("lat", 12.9716), loc.get("lng", 77.5946)))

    # 2. Get durations matrix
    matrix = get_distance_matrix(coords)
    if not matrix or len(matrix) != len(coords):
        # Fallback to straight distance ordering if durations table fails
        def dist(t):
            loc = t.get("location", {})
            return (loc.get("lat", 12.9716) - start_lat)**2 + (loc.get("lng", 77.5946) - start_lng)**2
        return sorted(tasks, key=dist)

    # 3. Nearest Neighbor traversal
    unvisited = list(range(1, len(coords)))
    current_node = 0 # start at origin (0)
    ordered_sequence = []

    while unvisited:
        # Find closest unvisited node
        best_next = None
        best_duration = float("inf")
        for node in unvisited:
            dur = matrix[current_node][node]
            if dur < best_duration:
                best_duration = dur
                best_next = node
                
        ordered_sequence.append(tasks[best_next - 1])
        unvisited.remove(best_next)
        current_node = best_next

    return ordered_sequence
