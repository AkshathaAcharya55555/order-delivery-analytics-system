package com.orderdelivery.deliveryservice.repository;

import com.orderdelivery.deliveryservice.entity.Location;
import org.springframework.data.jpa.repository.JpaRepository;

public interface LocationRepository extends JpaRepository<Location, Long> {
}
