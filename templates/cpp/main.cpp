#include <lcmware/topic.hpp>
#include "msg/point_array.hpp"

int main(int argc, char** argv)
{
    TopicPublisher<custom_package::PointArray> publisher("/points");

    while (true)
    {
        custom_package::PointArray msg;
        msg.points.resize(10);
        
        for (int i = 0; i < 10; ++i)
        {
            msg.points[i].x = i * 0.1f;
            msg.points[i].y = i * 0.2f;
        }

        publisher.publish(msg);
    }
    
}