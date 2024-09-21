import argparse
import time
import matplotlib.pyplot as plt

from utils import transform_trajectory_with_angles

from map.parking_lot import ParkingLot
from map.fixed_grid_map import FixedGridMap
from map.random_grid_map import RandomGridMap

from route_planner.geometry import Pose
from route_planner.informed_trrt_star_planner import InformedTRRTStar

from controller.mpc_controller import MPCController
from controller.adaptive_mpc_controller import AdaptiveMPCController
from controller.pure_pursuit_controller import PurePursuitController
from controller.hybrid_mi_controller import HybridMIController
from controller.multi_purpose_mpc_controller import MultiPurposeMPCController
from controller.stanley_controller import StanleyController

# 메인 함수
def main():
    parser = argparse.ArgumentParser(description="Controller Speed Test with Informed TRRT* Route Planner.")
    parser.add_argument('--map', type=str, default='fixed_grid', choices=['parking_lot', 'fixed_grid', 'random_grid'], help='Choose the map type.')
    args = parser.parse_args()

    # Map selection using dictionary
    map_options = {
        'parking_lot': ParkingLot,
        'fixed_grid': FixedGridMap,
        'random_grid': RandomGridMap
    }
    map_instance = map_options[args.map]()

    if args.map == "parking_lot":
        start_pose = Pose(14.0, 4.0, 0)
        goal_pose = Pose(50.0, 38.0, 1.57)
    elif args.map == "fixed_grid":
        start_pose = Pose(3, 5, 0)
        goal_pose = Pose(15, 15, 0)
    else:
        start_pose = map_instance.get_random_valid_start_position()
        goal_pose = map_instance.get_random_valid_goal_position()
    print(f"Start planning (start {start_pose.x, start_pose.y}, end {goal_pose.x, goal_pose.y})")

    # show_process 변수로 show_process와 show_eclipse 제어
    show_process = True

    # Informed TRRT* Planner
    planner = InformedTRRTStar(start_pose, goal_pose, map_instance, show_eclipse=False)

    # 초기 경로 생성
    route_trajectorys, route_trajectory_opts = [], []
    count = 0

    while(True):
        if count >= 5:
            break

        isReached, total_distance, route_trajectory, route_trajectory_opt = planner.search_route(show_process=show_process)
        if not isReached:
            continue

        plt.clf()
        if show_process:
            map_instance.plot_map(title=f"Informed TRRT* Route Planner [{count}]")
            plt.plot(start_pose.x, start_pose.y, "og")
            plt.plot(goal_pose.x, goal_pose.y, "xb")
            plt.plot(route_trajectory[:, 0], route_trajectory[:, 1], "g--", label="Theta* Path")  # Green dashed line
            plt.plot(route_trajectory_opt[:, 0], route_trajectory_opt[:, 1], "-r", label="Informed TRRT Path")  # Red solid line
            plt.savefig(f"results/test_controller/route_{count}.png")

        route_trajectorys.append(route_trajectory)
        route_trajectory_opts.append(route_trajectory_opt)
        count += 1

    # Controller selection using dictionary
    horizon = 10  # MPC horizon
    dt = 0.1  # Time step
    wheelbase = 2.5  # Example wheelbase of the vehicle in meters
    goal_position = [goal_pose.x, goal_pose.y]
    algorithms = {
        'pure_pursuit': lambda: PurePursuitController(lookahead_distance=5.0, dt=dt, wheelbase=wheelbase, map_instance=map_instance).follow_trajectory(start_pose, ref_trajectory, goal_position, show_process=show_process),
        'mpc_basic': lambda: MPCController(horizon=horizon, dt=dt, wheelbase=wheelbase, map_instance=map_instance).follow_trajectory(start_pose, ref_trajectory, goal_position, show_process=show_process),
        'adaptive_mpc': lambda: AdaptiveMPCController(horizon=horizon, dt=dt, wheelbase=wheelbase, map_instance=map_instance).follow_trajectory(start_pose, ref_trajectory, goal_position, show_process=show_process),
        'hybrid_mi': lambda: HybridMIController(horizon=horizon, dt=dt, wheelbase=wheelbase, map_instance=map_instance).follow_trajectory(start_pose, ref_trajectory, goal_position, show_process=show_process),
        # 'multi_purpose_mpc': lambda: MultiPurposeMPCController(horizon=horizon, dt=dt, wheelbase=wheelbase, map_instance=map_instance).follow_trajectory(start_pose, ref_trajectory, goal_position, show_process=show_process),
        # 'stanley': lambda: StanleyController(k=0.1, dt=dt, wheelbase=wheelbase, map_instance=map_instance).follow_trajectory(start_pose, ref_trajectory, goal_position, show_process=show_process),
    }

    # 각 알고리즘의 성능 측정 및 실패 여부 확인
    performance_results = {}
    distance_results = {}
    fail_counts = {name: 0 for name in algorithms}

    for name, func in algorithms.items():
        count = 0
        total_time = 0
        total_dist = 0
        is_reached = False
        while(True):  # 10번 반복 실행
            if count >= 5:
                break

            plt.clf()
            if show_process:
                map_instance.plot_map(title=f"{name} Controller [{count}]")
                plt.plot(start_pose.x, start_pose.y, "og")
                plt.plot(goal_pose.x, goal_pose.y, "xb")
                plt.plot(route_trajectorys[count][:, 0], route_trajectorys[count][:, 1], "g--", label="Theta* Path")  # Green dashed line
                plt.plot(route_trajectory_opts[count][:, 0], route_trajectory_opts[count][:, 1], "-r", label="Informed TRRT Path")  # Red solid line

            # 경로가 유효한 경우 컨트롤러 실행
            ref_trajectory = transform_trajectory_with_angles(route_trajectory_opts[count])
            start_time = time.time()
            is_reached, trajectory_distance, trajectory = func()
            end_time = time.time()
            control_time = end_time - start_time

            if show_process:
                plt.plot(trajectory[:, 0], trajectory[:, 1], "b-", label="Controller Path")
                plt.savefig(f"results/test_controller/controller_{name}_{count}.png")

            if not is_reached:
                fail_counts[name] += 1
            else:
                total_time += control_time
                total_dist += trajectory_distance
            
            count += 1

        if count - fail_counts[name] != 0:
            performance_results[name] = total_time / (count - fail_counts[name])  # 평균 실행 시간 계산
            distance_results[name] = total_dist / (count - fail_counts[name])
            print(f"{name}: {performance_results[name]:.6f} s (평균)")
            print(f"{name}: {distance_results[name]:.6f} m (평균)")

    # 성능 결과 정렬 및 출력
    sorted_performs = sorted(performance_results.items(), key=lambda x: x[1])
    for name, time_taken in sorted_performs:
        print(f"{name}: {time_taken:.6f} 초 (평균)")
    sorted_dists = sorted(distance_results.items(), key=lambda x: x[1])
    for name, dist in sorted_dists:
        print(f"{name}: {dist:.6f} m (평균)")

    # Plot the two charts side-by-side
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(20, 6))  # 1 row, 2 columns

    # Failure Counts Plot
    algorithm_names = list(fail_counts.keys())
    fail_values = list(fail_counts.values())
    ax1.barh(algorithm_names, fail_values, color='red')
    ax1.set_xlabel("Fail Count")
    ax1.set_ylabel("Algorithm")
    ax1.set_title("Algorithm Pathfinding Failure Counts (5 Runs)")
    ax1.grid(True)

    # Performance Results Plot
    algorithm_names = [result[0] for result in sorted_performs]
    times = [result[1] for result in sorted_performs]
    ax2.barh(algorithm_names, times, color='skyblue')
    ax2.set_xlabel("Average Execution Time (seconds)")
    ax2.set_title("Algorithm Performance Comparison (10 Runs)")
    ax2.grid(True)

    # Performance Results Plot
    algorithm_names = [result[0] for result in sorted_dists]
    dists = [result[1] for result in sorted_dists]
    ax3.barh(algorithm_names, dists, color='purple')
    ax3.set_xlabel("Average Trajectory Distance (m)")
    ax3.set_title("Algorithm Performance Comparison (10 Runs)")
    ax3.grid(True)

    # Adjust layout and show plot
    plt.tight_layout()  # Ensure there's enough space between the plots
    plt.savefig("results/test_route_planner/performance_route_planner.png")
    plt.show()

if __name__ == "__main__":
    main()
