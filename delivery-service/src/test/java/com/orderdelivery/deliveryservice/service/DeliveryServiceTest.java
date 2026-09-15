package com.orderdelivery.deliveryservice.service;

import com.orderdelivery.deliveryservice.entity.Delivery;
import com.orderdelivery.deliveryservice.entity.Location;
import com.orderdelivery.deliveryservice.entity.Order;
import com.orderdelivery.deliveryservice.entity.Rider;
import com.orderdelivery.deliveryservice.event.EventPublisher;
import com.orderdelivery.deliveryservice.exception.InvalidStateException;
import com.orderdelivery.deliveryservice.exception.NoAvailableRiderException;
import com.orderdelivery.deliveryservice.exception.ResourceNotFoundException;
import com.orderdelivery.deliveryservice.model.DeliveryStatus;
import com.orderdelivery.deliveryservice.model.OrderStatus;
import com.orderdelivery.deliveryservice.repository.DeliveryRepository;
import com.orderdelivery.deliveryservice.repository.LocationRepository;
import com.orderdelivery.deliveryservice.repository.OrderRepository;
import com.orderdelivery.deliveryservice.repository.OrderStatusHistoryRepository;
import com.orderdelivery.deliveryservice.repository.RiderRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class DeliveryServiceTest {

    @Mock private DeliveryRepository deliveryRepository;
    @Mock private RiderRepository riderRepository;
    @Mock private OrderRepository orderRepository;
    @Mock private LocationRepository locationRepository;
    @Mock private OrderStatusHistoryRepository historyRepository;

    // Plain no-op subclass rather than @Mock: Mockito's inline mock maker
    // cannot instrument concrete classes on Java 25 in this environment.
    private final EventPublisher eventPublisher = new EventPublisher(null, null) {
        @Override
        public void publishRiderAssigned(Long orderId, java.util.Map<String, Object> payload) {
        }

        @Override
        public void publishDeliveryStarted(Long orderId, java.util.Map<String, Object> payload) {
        }

        @Override
        public void publishDeliveryCompleted(Long orderId, java.util.Map<String, Object> payload) {
        }

        @Override
        public void publishDeliveryFailed(Long orderId, java.util.Map<String, Object> payload) {
        }
    };

    private DeliveryService deliveryService;

    @BeforeEach
    void setUp() {
        deliveryService = new DeliveryService(deliveryRepository, riderRepository, orderRepository,
                locationRepository, historyRepository, new RiderMatcher(), eventPublisher);
    }

    private Order orderWithStatus(Long id, OrderStatus status, Long locationId) throws Exception {
        Order order = newInstance(Order.class);
        setField(order, "orderId", id);
        setField(order, "deliveryLocationId", locationId);
        setField(order, "status", status);
        return order;
    }

    private static <T> T newInstance(Class<T> type) throws Exception {
        Constructor<T> ctor = type.getDeclaredConstructor();
        ctor.setAccessible(true);
        return ctor.newInstance();
    }

    private static void setField(Object target, String name, Object value) throws Exception {
        Field field = target.getClass().getDeclaredField(name);
        field.setAccessible(true);
        field.set(target, value);
    }

    @Test
    void assignRider_success_picksMatchingRiderAndUpdatesOrder() throws Exception {
        Order order = orderWithStatus(1L, OrderStatus.READY_FOR_PICKUP, 10L);
        Location location = newInstance(Location.class);
        setField(location, "locationId", 10L);
        setField(location, "city", "Austin");
        setField(location, "latitude", new BigDecimal("30.2672"));
        setField(location, "longitude", new BigDecimal("-97.7431"));

        Rider rider = new Rider("A", "B", "555-0000", "bike", "Austin", new BigDecimal("4.5"),
                LocalDate.now(), new BigDecimal("30.2672"), new BigDecimal("-97.7431"));
        setField(rider, "riderId", 100L); // normally assigned by the DB on persist

        when(orderRepository.findById(1L)).thenReturn(Optional.of(order));
        when(deliveryRepository.findByOrderId(1L)).thenReturn(Optional.empty());
        when(locationRepository.findById(10L)).thenReturn(Optional.of(location));
        when(riderRepository.findByCityAndActiveTrueAndAvailableTrue("Austin")).thenReturn(List.of(rider));
        when(deliveryRepository.countActiveDeliveriesGroupedByRider(any(), any())).thenReturn(List.of());
        when(deliveryRepository.save(any(Delivery.class))).thenAnswer(inv -> inv.getArgument(0));
        when(orderRepository.save(any(Order.class))).thenAnswer(inv -> inv.getArgument(0));

        Delivery result = deliveryService.assignRider(1L);

        assertThat(result.getDeliveryStatus()).isEqualTo(DeliveryStatus.ASSIGNED);
        assertThat(order.getStatus()).isEqualTo(OrderStatus.RIDER_ASSIGNED);
        assertThat(order.getRiderId()).isNotNull();
        verify(historyRepository).save(any());
    }

    @Test
    void assignRider_orderAlreadyDelivered_throwsInvalidState() throws Exception {
        Order order = orderWithStatus(2L, OrderStatus.DELIVERED, 10L);
        when(orderRepository.findById(2L)).thenReturn(Optional.of(order));

        assertThatThrownBy(() -> deliveryService.assignRider(2L))
                .isInstanceOf(InvalidStateException.class);
    }

    @Test
    void assignRider_alreadyHasDelivery_throwsInvalidState() throws Exception {
        Order order = orderWithStatus(3L, OrderStatus.READY_FOR_PICKUP, 10L);
        Delivery existing = new Delivery(3L, 1L, java.time.LocalDateTime.now(), DeliveryStatus.ASSIGNED, BigDecimal.ONE);
        when(orderRepository.findById(3L)).thenReturn(Optional.of(order));
        when(deliveryRepository.findByOrderId(3L)).thenReturn(Optional.of(existing));

        assertThatThrownBy(() -> deliveryService.assignRider(3L))
                .isInstanceOf(InvalidStateException.class);
    }

    @Test
    void assignRider_noCandidatesInCity_throwsNoAvailableRider() throws Exception {
        Order order = orderWithStatus(4L, OrderStatus.READY_FOR_PICKUP, 10L);
        Location location = newInstance(Location.class);
        setField(location, "locationId", 10L);
        setField(location, "city", "Miami");
        setField(location, "latitude", new BigDecimal("25.7617"));
        setField(location, "longitude", new BigDecimal("-80.1918"));

        when(orderRepository.findById(4L)).thenReturn(Optional.of(order));
        when(deliveryRepository.findByOrderId(4L)).thenReturn(Optional.empty());
        when(locationRepository.findById(10L)).thenReturn(Optional.of(location));
        when(riderRepository.findByCityAndActiveTrueAndAvailableTrue("Miami")).thenReturn(List.of());

        assertThatThrownBy(() -> deliveryService.assignRider(4L))
                .isInstanceOf(NoAvailableRiderException.class);
    }

    @Test
    void assignRider_batchedWorkloadQuery_attributesCountsToCorrectRider() throws Exception {
        // Proves the batched countActiveDeliveriesGroupedByRider result is
        // correctly matched back to the RIGHT rider by id (not just a flat
        // default) - added when the per-rider N+1 query was replaced with
        // one batched query (see docs/FINAL_AUDIT.md).
        record TestWorkload(Long riderId, Long activeCount) implements DeliveryRepository.RiderWorkloadCount {
            public Long getRiderId() {
                return riderId;
            }

            public Long getActiveCount() {
                return activeCount;
            }
        }

        Order order = orderWithStatus(10L, OrderStatus.READY_FOR_PICKUP, 20L);
        Location location = newInstance(Location.class);
        setField(location, "locationId", 20L);
        setField(location, "city", "Chicago");
        setField(location, "latitude", new BigDecimal("41.8781"));
        setField(location, "longitude", new BigDecimal("-87.6298"));

        // Both riders at the exact same position (same distance to the
        // order) - so only workload can break the tie.
        Rider busyRider = new Rider("Busy", "Rider", "555-0001", "bike", "Chicago", new BigDecimal("4.5"),
                LocalDate.now(), new BigDecimal("41.8781"), new BigDecimal("-87.6298"));
        setField(busyRider, "riderId", 201L);
        Rider idleRider = new Rider("Idle", "Rider", "555-0002", "bike", "Chicago", new BigDecimal("4.5"),
                LocalDate.now(), new BigDecimal("41.8781"), new BigDecimal("-87.6298"));
        setField(idleRider, "riderId", 202L);

        when(orderRepository.findById(10L)).thenReturn(Optional.of(order));
        when(deliveryRepository.findByOrderId(10L)).thenReturn(Optional.empty());
        when(locationRepository.findById(20L)).thenReturn(Optional.of(location));
        when(riderRepository.findByCityAndActiveTrueAndAvailableTrue("Chicago")).thenReturn(List.of(busyRider, idleRider));
        // Only the busy rider (201) has a row - the idle rider (202) has none,
        // and must default to a workload of 0, not be skipped or mis-matched.
        when(deliveryRepository.countActiveDeliveriesGroupedByRider(any(), any()))
                .thenReturn(List.of(new TestWorkload(201L, 5L)));
        when(deliveryRepository.save(any(Delivery.class))).thenAnswer(inv -> inv.getArgument(0));
        when(orderRepository.save(any(Order.class))).thenAnswer(inv -> inv.getArgument(0));

        Delivery result = deliveryService.assignRider(10L);

        assertThat(result.getRiderId()).isEqualTo(202L); // the idle rider must win, not the busy one
    }

    @Test
    void updateStatus_illegalTransition_throwsInvalidState() {
        Delivery delivery = new Delivery(5L, 1L, java.time.LocalDateTime.now(), DeliveryStatus.ASSIGNED, BigDecimal.ONE);
        when(deliveryRepository.findByOrderId(5L)).thenReturn(Optional.of(delivery));

        // ASSIGNED cannot go straight to DELIVERED
        assertThatThrownBy(() -> deliveryService.updateStatus(5L, DeliveryStatus.DELIVERED))
                .isInstanceOf(InvalidStateException.class);
    }

    @Test
    void updateStatus_missingDelivery_throwsNotFound() {
        when(deliveryRepository.findByOrderId(99L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> deliveryService.updateStatus(99L, DeliveryStatus.PICKED_UP))
                .isInstanceOf(ResourceNotFoundException.class);
    }

    @Test
    void updateStatus_legalTransition_updatesDeliveryAndOrder() throws Exception {
        Delivery delivery = new Delivery(6L, 1L, java.time.LocalDateTime.now(), DeliveryStatus.ASSIGNED, BigDecimal.ONE);
        Order order = orderWithStatus(6L, OrderStatus.RIDER_ASSIGNED, 10L);

        when(deliveryRepository.findByOrderId(6L)).thenReturn(Optional.of(delivery));
        when(deliveryRepository.save(any(Delivery.class))).thenAnswer(inv -> inv.getArgument(0));
        when(orderRepository.findById(6L)).thenReturn(Optional.of(order));
        when(orderRepository.save(any(Order.class))).thenAnswer(inv -> inv.getArgument(0));

        Delivery result = deliveryService.updateStatus(6L, DeliveryStatus.PICKED_UP);

        assertThat(result.getDeliveryStatus()).isEqualTo(DeliveryStatus.PICKED_UP);
        assertThat(result.getPickedUpAt()).isNotNull();
        assertThat(order.getStatus()).isEqualTo(OrderStatus.PICKED_UP);
    }
}
